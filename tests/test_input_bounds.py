"""Input bounds and error reporting for file input."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_replay_bundle.ingress import (
    InputBoundsError,
    check_depth,
    load_json_bounded,
    read_bounded_text,
)
from agent_replay_bundle.loader import load_replay_bundle
from agent_replay_bundle.signing import sign_replay_bundle

EXAMPLES = Path(__file__).parent.parent / "examples"
VALID = EXAMPLES / "customer_service_replay_bundle.json"


def run_arb(*args):
    r = subprocess.run(
        [sys.executable, "-I", "-m", "agent_replay_bundle.cli", *args],
        capture_output=True,
        text=True,
    )
    return r.returncode, r.stdout, r.stderr


def _deep(n):
    return "[" * n + "]" * n


@pytest.mark.parametrize("cmd", ["validate", "summarize"])
def test_deep_input_has_distinct_exit_code(tmp_path, cmd):
    p = tmp_path / "deep.json"
    p.write_text(_deep(200000))
    rc, out, err = run_arb(cmd, str(p))
    assert rc == 3
    assert "nesting_depth_exceeded" in err
    assert "Traceback" not in err


def test_deep_input_verify(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text(_deep(200000))
    rc, out, err = run_arb("verify", str(p), "--secret", "s")
    assert rc == 3
    assert "Traceback" not in err


def test_byte_budget(tmp_path):
    p = tmp_path / "big.json"
    p.write_text('"' + "a" * 100 + '"')
    with pytest.raises(InputBoundsError) as ei:
        read_bounded_text(p, max_bytes=50)
    assert ei.value.code == "input_too_large"


def test_depth_at_limit_is_accepted_and_brackets_in_strings_ignored():
    check_depth(_deep(128))
    with pytest.raises(InputBoundsError):
        check_depth(_deep(129))
    check_depth(json.dumps({"a": "[" * 1000 + '\\"' + "{" * 1000}))


def test_loader_raises_typed_error(tmp_path):
    p = tmp_path / "deep.json"
    p.write_text(_deep(1000))
    with pytest.raises(InputBoundsError):
        load_replay_bundle(p)


def test_valid_example_unchanged(tmp_path):
    assert run_arb("validate", str(VALID))[0] == 0
    assert load_json_bounded(VALID) == json.loads(VALID.read_text(encoding="utf-8"))


def _signed(tmp_path):
    b = load_replay_bundle(VALID)
    s = sign_replay_bundle(b, "s3", key_id="k")
    p = tmp_path / "signed.json"
    p.write_text(json.dumps(s.model_dump(mode="json")), encoding="utf-8")
    return p


def test_verify_valid_unchanged(tmp_path):
    p = _signed(tmp_path)
    rc, out, _ = run_arb("verify", str(p), "--secret", "s3")
    assert rc == 0 and "VALID" in out
    assert run_arb("verify", str(p), "--secret", "bad")[0] == 1


def test_verify_refuses_repeated_member(tmp_path):
    p = _signed(tmp_path)
    raw = p.read_text(encoding="utf-8")
    p.write_text('{"signed_bundle_id": "x", ' + raw[1:], encoding="utf-8")
    rc, out, err = run_arb("verify", str(p), "--secret", "s3")
    assert rc == 2
    assert "duplicate member" in err


def test_load_keeps_last_value_for_repeated_member(tmp_path):
    raw = VALID.read_text(encoding="utf-8")
    first = json.loads(raw)["bundle_id"]
    p = tmp_path / "dup.json"
    p.write_text('{"bundle_id": "first-value", ' + raw.strip()[1:], encoding="utf-8")
    assert load_replay_bundle(p).bundle_id == first


def test_envelope_members_outside_signature_scope(tmp_path):
    """Documented in docs/signing.md; pinned so a change is deliberate."""
    p = _signed(tmp_path)
    d = json.loads(p.read_text())
    d["signed_bundle_id"] = "other"
    d["signature_metadata"]["key_id"] = "other"
    d["signature_metadata"]["signed_at"] = "2000-01-01T00:00:00Z"
    p.write_text(json.dumps(d))
    assert run_arb("verify", str(p), "--secret", "s3")[0] == 0
