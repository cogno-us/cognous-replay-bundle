"""0.2.0 reconstruction bundles: the HMAC and the content digest cover only the model dump, so a file that carries members
the model drops, or scalars it coerces, is refused by the raw-JSON verifiers and by ``arb verify-reconstruction``."""
import copy
import json
from pathlib import Path

from agent_replay_bundle import cli
from agent_replay_bundle.reconstruction import (
    ReconstructionBundle,
    SourceRecord,
    redact_reconstruction_bundle,
    sign_reconstruction_bundle,
    verify_content_digest,
    verify_content_digest_raw,
    verify_reconstruction_hmac,
    verify_reconstruction_hmac_raw,
)

from .test_input_bounds import run_arb

EXAMPLES = Path(__file__).parent.parent / "examples"
SECRET = "sec"


def _bundle():
    return ReconstructionBundle(
        bundle_id="b1",
        run_id="r",
        records=[SourceRecord(record_id="x", producer_profile_id="p", record_type="t", source_sequence=1,
                              source_path="a", data={"k": 1})],
    )


def _signed_raw():
    return json.loads(json.dumps(sign_reconstruction_bundle(_bundle(), SECRET, key_id="k").model_dump(mode="json")))


def _digest_raw():
    return json.loads(json.dumps(redact_reconstruction_bundle(_bundle(), redact_paths={"a"}).model_dump(mode="json")))


INJECTIONS = {
    "top": lambda d: d.update(approved_by="ceo"),
    "record": lambda d: d["records"][0].update(authorized=True),
    "semantics": lambda d: d["semantics"].update(effect_verified=True),
    "integrity": lambda d: d["integrity"][0].update(issuer="trusted-ca"),
}


def test_controls_clean_files_verify():
    assert verify_reconstruction_hmac_raw(_signed_raw(), SECRET) is True
    assert verify_content_digest_raw(_digest_raw()) is True


def test_parsed_model_verifiers_do_not_see_injected_members_documented_limit():
    raw = _signed_raw()
    for inject in INJECTIONS.values():
        inject(raw)
    assert verify_reconstruction_hmac(ReconstructionBundle.model_validate(raw), SECRET) is True  # the limit the docs record
    assert verify_reconstruction_hmac_raw(raw, SECRET) is False


def test_each_injected_member_is_refused_by_the_raw_hmac_verifier():
    for name, inject in INJECTIONS.items():
        raw = _signed_raw()
        inject(raw)
        assert verify_reconstruction_hmac_raw(raw, SECRET) is False, name


def test_injected_member_is_refused_by_the_raw_digest_verifier():
    raw = _digest_raw()
    raw["records"][0]["note"] = "unreviewed"
    assert verify_content_digest(ReconstructionBundle.model_validate(raw)) is True  # the limit the docs record
    assert verify_content_digest_raw(raw) is False


def test_coerced_scalar_is_refused():
    raw = _signed_raw()
    raw["records"][0]["source_sequence"] = "1"  # pydantic lax mode reads this back as 1
    assert verify_reconstruction_hmac(ReconstructionBundle.model_validate(raw), SECRET) is True
    assert verify_reconstruction_hmac_raw(raw, SECRET) is False


def test_raw_verifiers_still_check_the_signature_and_the_digest():
    raw = _signed_raw()
    assert verify_reconstruction_hmac_raw(raw, "wrong") is False
    raw["run_id"] = "other"
    assert verify_reconstruction_hmac_raw(raw, SECRET) is False
    d = _digest_raw()
    d["run_id"] = "other"
    assert verify_content_digest_raw(d) is False
    assert verify_content_digest_raw({"bundle_version": "0.2.0", "records": "nope"}) is False


def test_digest_raw_required_flag():
    raw = _signed_raw()  # carries an hmac entry, no content-digest entry
    assert verify_content_digest_raw(raw, required=False) is True
    assert verify_content_digest_raw(raw) is False


def _write(tmp_path, raw, name="r.json"):
    p = tmp_path / name
    p.write_text(json.dumps(raw), encoding="utf-8")
    return str(p)


def test_cli_verify_reconstruction_valid_and_refusals(tmp_path):
    rc, out, _ = run_arb("verify-reconstruction", _write(tmp_path, _signed_raw()), "--secret", SECRET)
    assert rc == 0 and "HMAC VALID" in out
    rc, out, _ = run_arb("verify-reconstruction", _write(tmp_path, _signed_raw()), "--secret", "wrong")
    assert rc == 1 and "HMAC INVALID" in out
    rc, out, _ = run_arb("verify-reconstruction", _write(tmp_path, _digest_raw()), "--require-digest")
    assert rc == 0 and "Content digest VALID" in out
    rc, _, err = run_arb("verify-reconstruction", _write(tmp_path, _digest_raw()))
    assert rc == 2 and "--secret" in err


def test_cli_verify_reconstruction_refuses_injected_members(tmp_path):
    for name, inject in INJECTIONS.items():
        raw = _signed_raw()
        inject(raw)
        rc, out, _ = run_arb("verify-reconstruction", _write(tmp_path, raw), "--secret", SECRET)
        assert rc == 1 and "INVALID" in out and "do not cover" in out and "VALID" not in out.replace("INVALID", ""), (name, out)


def test_cli_verify_reconstruction_refuses_bad_input(tmp_path):
    rc, _, err = run_arb("verify-reconstruction", _write(tmp_path, {"bundle_version": "0.2.0", "records": 3}), "--secret", SECRET)
    assert rc == 2 and "Invalid reconstruction bundle" in err
    rc, _, err = run_arb("verify-reconstruction", str(tmp_path / "missing.json"), "--secret", SECRET)
    assert rc == 2


def test_check_examples_refuses_a_reconstruction_example_with_an_extra_member(tmp_path, monkeypatch, capsys):
    ex = tmp_path / "examples"
    ex.mkdir()
    raw = json.loads((EXAMPLES / "bounded_success_reconstruction_v0_2.json").read_text(encoding="utf-8"))
    raw["approved_by"] = "ceo"
    (ex / "bounded_success_reconstruction_v0_2.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "x" / "y" / "cli.py"), raising=False)
    monkeypatch.chdir(tmp_path)
    rc = cli.cmd_check_examples(None)
    out = capsys.readouterr().out
    assert rc == 1 and "approved_by" in out


def test_shipped_reconstruction_examples_carry_no_unretained_members():
    for p in EXAMPLES.glob("*.json"):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("bundle_version") == "0.2.0":
            bundle = ReconstructionBundle.model_validate(copy.deepcopy(raw))
            from agent_replay_bundle.reconstruction import reconstruction_unretained_members

            assert reconstruction_unretained_members(raw, bundle) == [], p.name
