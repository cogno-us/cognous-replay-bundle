"""``verify_content_digest`` fails closed on a stale or malformed content-digest entry; ``arb check-examples`` uses it."""
import json
from pathlib import Path

import pytest

from agent_replay_bundle import cli
from agent_replay_bundle.reconstruction import (
    ReconstructionBundle,
    content_digest,
    redact_reconstruction_bundle,
)

EXAMPLES = Path(__file__).parent.parent / "examples"
SOURCE = EXAMPLES / "bounded_success_reconstruction_v0_2.json"


def _bundle():
    return ReconstructionBundle.model_validate(json.loads(SOURCE.read_text(encoding="utf-8")))


def _with_digest():
    from agent_replay_bundle.reconstruction import verify_content_digest  # noqa: F401  (import fails on old code)

    bundle = _bundle()
    bundle.integrity = [content_digest(bundle)]
    return bundle


def test_matching_digest_verifies_and_redacted_derivative_verifies():
    from agent_replay_bundle.reconstruction import verify_content_digest

    bundle = _with_digest()
    assert verify_content_digest(bundle) is True
    path = bundle.records[0].source_path
    assert verify_content_digest(redact_reconstruction_bundle(bundle, redact_paths={path})) is True


def test_stale_digest_after_content_change_is_refused():
    from agent_replay_bundle.reconstruction import verify_content_digest

    bundle = _with_digest()
    bundle.records[0].data = {"tampered": True}
    assert verify_content_digest(bundle) is False
    assert verify_content_digest(bundle, required=False) is False
    # the stale bundle still loads: loading is not the check
    ReconstructionBundle.model_validate(bundle.model_dump(mode="json"))


@pytest.mark.parametrize("edit", [
    lambda b: setattr(b.integrity[0], "value", "sha256:" + "0" * 64),
    lambda b: setattr(b.integrity[0], "subject_bundle_id", "other"),
    lambda b: setattr(b.integrity[0], "canonicalization_profile", "other"),
    lambda b: b.integrity.append(b.integrity[0].model_copy()),
])
def test_malformed_entries_fail_closed(edit):
    from agent_replay_bundle.reconstruction import verify_content_digest

    bundle = _with_digest()
    edit(bundle)
    assert verify_content_digest(bundle) is False


def test_absent_entry_fails_when_required_and_passes_when_optional():
    from agent_replay_bundle.reconstruction import verify_content_digest

    bundle = _bundle()
    assert bundle.integrity == []
    assert verify_content_digest(bundle) is False
    assert verify_content_digest(bundle, required=False) is True


def test_check_examples_fails_a_reconstruction_example_with_a_stale_digest(tmp_path, monkeypatch, capsys):
    fake_module = tmp_path / "pkg" / "sub" / "cli.py"
    fake_module.parent.mkdir(parents=True)
    monkeypatch.setattr(cli, "__file__", str(fake_module))
    examples = tmp_path / "examples"
    examples.mkdir()
    good = json.loads(SOURCE.read_text(encoding="utf-8"))
    (examples / "ok.json").write_text(json.dumps(good), encoding="utf-8")
    bundle = _bundle()
    bundle.integrity = [content_digest(bundle)]
    stale = bundle.model_dump(mode="json")
    stale["records"][0]["data"] = {"tampered": True}
    (examples / "stale.json").write_text(json.dumps(stale), encoding="utf-8")
    assert cli.cmd_check_examples(None) == 1
    out = capsys.readouterr().out
    assert "OK (reconstruction) ok.json" in out
    assert "FAIL" in out and "stale.json" in out and "content-digest" in out
