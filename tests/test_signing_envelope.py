"""Export integrity signing: a new signature covers the signed envelope (``signed_bundle_id`` and the ``signature_metadata``
fields) and the embedded ``signature_metadata`` of the inner bundle; an earlier, bundle-only signature still verifies and is
reported as not covering them."""
import hashlib
import hmac
import json

import pytest

from agent_replay_bundle.models import SignatureMetadata, SignedReplayBundle
from agent_replay_bundle.signing import (
    canonical_bundle_json,
    sign_replay_bundle,
    signature_coverage,
    verify_signed_replay_bundle,
)

from .test_input_bounds import VALID, run_arb
from .test_signing import make_bundle


def legacy_sign(bundle, secret, key_id="k"):
    """A signature as written before the envelope was covered: HMAC over the canonical inner bundle only."""
    digest = hmac.new(secret.encode(), canonical_bundle_json(bundle).encode(), hashlib.sha256).hexdigest()
    meta = SignatureMetadata(signed=True, signed_at="2026-01-01T00:00:00Z", signature_algorithm="HMAC-SHA256",
                             signature=digest, key_id=key_id)
    return SignedReplayBundle(signed_bundle_id="signed-legacy", replay_bundle=bundle, signature_metadata=meta)


def changed(signed, change):
    data = json.loads(signed.model_dump_json())
    change(data)
    return SignedReplayBundle.model_validate(data)


# ---------------------------------------------------------------------------------------------------- controls
def test_control_a_new_signature_verifies_and_reports_envelope_coverage():
    signed = sign_replay_bundle(make_bundle(), "s3", key_id="k")
    assert verify_signed_replay_bundle(signed, "s3") is True
    assert signature_coverage(signed, "s3") == "envelope_and_bundle"
    assert verify_signed_replay_bundle(signed, "other") is False
    assert signature_coverage(signed, "other") is None


def test_control_a_bundle_only_signature_still_verifies_and_is_reported_as_such():
    signed = legacy_sign(make_bundle(), "s3")
    assert verify_signed_replay_bundle(signed, "s3") is False  # refused by default
    assert verify_signed_replay_bundle(signed, "s3", allow_unbound_envelope=True) is True
    assert signature_coverage(signed, "s3") == "bundle_only"
    assert verify_signed_replay_bundle(signed, "s3", allow_unbound_envelope=False) is False
    assert verify_signed_replay_bundle(signed, "other") is False


def test_control_a_bundle_only_signature_keeps_its_documented_limit():
    """The earlier limit, pinned for earlier signatures only: its envelope members are not covered."""
    signed = legacy_sign(make_bundle(), "s3")
    other = changed(signed, lambda d: d.update(signed_bundle_id="other"))
    assert verify_signed_replay_bundle(other, "s3", allow_unbound_envelope=True) is True and signature_coverage(other, "s3") == "bundle_only"


# ---------------------------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize("name,change", [
    ("signed_bundle_id", lambda d: d.update(signed_bundle_id="other")),
    ("key_id", lambda d: d["signature_metadata"].update(key_id="other")),
    ("signed_at", lambda d: d["signature_metadata"].update(signed_at="2000-01-01T00:00:00Z")),
    ("signature_algorithm", lambda d: d["signature_metadata"].update(signature_algorithm="HMAC-SHA512")),
    ("key_id_removed", lambda d: d["signature_metadata"].update(key_id=None)),
    ("embedded_signature_metadata_added", lambda d: d["replay_bundle"].update(
        signature_metadata={"signed": True, "signature": "a" * 64, "signature_algorithm": "HMAC-SHA256"})),
    ("inner_content", lambda d: d["replay_bundle"].update(final_output="changed")),
])
def test_a_changed_envelope_member_is_not_accepted(name, change):
    signed = sign_replay_bundle(make_bundle(), "s3", key_id="k")
    damaged = changed(signed, change)
    assert verify_signed_replay_bundle(damaged, "s3") is False
    assert signature_coverage(damaged, "s3") is None


def test_the_embedded_signature_metadata_of_the_inner_bundle_is_covered():
    bundle = make_bundle(signature_metadata=SignatureMetadata(signed=True, signed_at="2026-01-01T00:00:01Z", signature="e" * 64,
                                                              signature_algorithm="HMAC-SHA256", key_id="embedded"))
    signed = sign_replay_bundle(bundle, "s3")
    assert verify_signed_replay_bundle(signed, "s3") is True
    damaged = changed(signed, lambda d: d["replay_bundle"]["signature_metadata"].update(key_id="other"))
    assert verify_signed_replay_bundle(damaged, "s3") is False


def test_a_new_signature_is_not_a_valid_bundle_only_signature():
    signed = sign_replay_bundle(make_bundle(), "s3")
    assert signed.signature_metadata.signature != legacy_sign(signed.replay_bundle, "s3").signature_metadata.signature


# ----------------------------------------------------------------------------------------------------------- CLI
def _write(tmp_path, signed):
    path = tmp_path / "signed.json"
    path.write_text(signed.model_dump_json(), encoding="utf-8")
    return path


def test_cli_signs_with_envelope_coverage_and_refuses_a_changed_envelope(tmp_path):
    out = tmp_path / "signed.json"
    assert run_arb("sign", str(VALID), "--secret", "s3", "--out", str(out), "--key-id", "k")[0] == 0
    assert run_arb("verify", str(out), "--secret", "s3")[0] == 0
    data = json.loads(out.read_text())
    data["signature_metadata"]["key_id"] = "other"
    out.write_text(json.dumps(data))
    rc, text, _ = run_arb("verify", str(out), "--secret", "s3")
    assert rc == 1 and "INVALID" in text


def test_cli_accepts_a_bundle_only_signature_with_a_note_and_can_refuse_it(tmp_path):
    from agent_replay_bundle.loader import load_replay_bundle
    path = _write(tmp_path, legacy_sign(load_replay_bundle(VALID), "s3"))
    rc, text, err = run_arb("verify", str(path), "--secret", "s3")
    assert rc == 1 and "NOT ACCEPTED" in text and "--allow-unbound-envelope" in text
    rc, text, err = run_arb("verify", str(path), "--secret", "s3", "--allow-unbound-envelope")
    assert rc == 0 and "VALID" in text and "not covered" in err
    rc, text, err = run_arb("verify", str(path), "--secret", "s3", "--require-bound-envelope")
    assert rc == 1 and "INVALID" not in text.replace("NOT ACCEPTED", "") and "not covered" in (text + err)
