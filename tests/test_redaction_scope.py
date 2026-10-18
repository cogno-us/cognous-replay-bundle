"""Redaction options that cover the task text, the scope fields and the embedded signature metadata (all off by default)."""
from agent_replay_bundle.models import AuthorityRecord, RelianceRecord, SignatureMetadata
from agent_replay_bundle.redaction import redact_replay_bundle

from .test_redaction import make_full_bundle
from .test_input_bounds import VALID, run_arb


def scoped_bundle():
    bundle = make_full_bundle()
    bundle.reliance_records = [RelianceRecord(reliance_id="rel-1", run_id="run-001", source_name="crm", source_type="database",
                                              scope="customer 4411 billing address", created_at="2026-01-01T00:00:00Z")]
    bundle.authority_records = [AuthorityRecord(authority_id="auth-1", run_id="run-001", actor="agent", source="user delegation",
                                                scope=["read:customer-4411", "refund:order-77"], created_at="2026-01-01T00:00:00Z")]
    bundle.signature_metadata = SignatureMetadata(signed=True, signed_at="2026-01-01T00:00:05Z", signature_algorithm="HMAC-SHA256",
                                                  signature="a" * 64, key_id="k")
    return bundle


def test_control_defaults_leave_task_scope_and_signature_as_before():
    out = redact_replay_bundle(scoped_bundle())
    assert out.frame.task == "Test task"
    assert out.reliance_records[0].scope == "customer 4411 billing address"
    assert out.authority_records[0].scope == ["read:customer-4411", "refund:order-77"]
    assert out.signature_metadata is not None and out.signature_metadata.signed is True


def test_task_text_is_redacted_on_request_and_listed():
    out = redact_replay_bundle(scoped_bundle(), redact_task=True)
    assert out.frame.task == "[REDACTED]"
    assert "frame.task" in out.redaction_metadata.redacted_fields
    assert out.frame.actor == "test-agent" and out.frame.frame_id == "frame-001"


def test_scope_fields_are_redacted_on_request_and_listed():
    out = redact_replay_bundle(scoped_bundle(), redact_scope=True, replacement="[X]")
    assert out.reliance_records[0].scope == "[X]"
    assert out.authority_records[0].scope == ["[X]"]
    assert {"reliance_records[0].scope", "authority_records[0].scope"} <= set(out.redaction_metadata.redacted_fields)
    assert out.reliance_records[0].reliance_id == "rel-1" and out.authority_records[0].authority_id == "auth-1"


def test_embedded_signature_metadata_is_dropped_on_request_and_listed():
    out = redact_replay_bundle(scoped_bundle(), clear_signature_metadata=True)
    assert out.signature_metadata is None
    assert "signature_metadata" in out.redaction_metadata.redacted_fields


def test_clearing_is_a_noop_for_a_bundle_without_signature_metadata():
    out = redact_replay_bundle(make_full_bundle(), clear_signature_metadata=True)
    assert out.signature_metadata is None and "signature_metadata" not in out.redaction_metadata.redacted_fields


def test_original_is_not_mutated():
    bundle = scoped_bundle()
    redact_replay_bundle(bundle, redact_task=True, redact_scope=True, clear_signature_metadata=True)
    assert bundle.frame.task == "Test task" and bundle.signature_metadata is not None


def test_cli_flags(tmp_path):
    out = tmp_path / "r.json"
    rc, _, err = run_arb("redact", str(VALID), "--out", str(out), "--task", "--scope", "--drop-signature")
    assert rc == 0, err
    import json
    data = json.loads(out.read_text())
    assert data["frame"]["task"] == "[REDACTED]"
    assert all(r["scope"] == "[REDACTED]" for r in data["reliance_records"])
    assert data.get("signature_metadata") is None
