"""Tests for the validator module."""

import pytest

from agent_replay_bundle.models import (
    ActionProposal,
    ActionType,
    AgentReplayBundle,
    AuthorityRecord,
    BlockedAction,
    DecisionResult,
    PolicyDecision,
    PolicyEvaluationTrace,
    PolicyRuleEvaluation,
    RedactionMetadata,
    RelianceRecord,
    RunFrame,
    SignatureMetadata,
    TraceRuleResult,
    ValidationSeverity,
)
from agent_replay_bundle.validator import validate_replay_bundle


def make_frame(**kwargs):
    defaults = {
        "frame_id": "frame-001",
        "task": "Test task",
        "actor": "test-agent",
        "environment": "test",
        "policy_version": "v1.0",
        "created_at": "2026-01-01T00:00:00Z",
        "allowed_tools": ["tool_a"],
        "blocked_tools": ["tool_b"],
    }
    defaults.update(kwargs)
    return RunFrame(**defaults)


def make_bundle(**kwargs):
    defaults = {
        "bundle_id": "bundle-001",
        "run_id": "run-001",
        "generated_at": "2026-01-01T00:00:00Z",
        "frame": make_frame(),
        "final_output": "Done.",
        "signature_metadata": SignatureMetadata(
            signed=False,
        ),
    }
    defaults.update(kwargs)
    return AgentReplayBundle(**defaults)


def make_proposal(**kwargs):
    defaults = {
        "action_id": "action-001",
        "run_id": "run-001",
        "tool_name": "tool_a",
        "action_type": ActionType.read,
        "target": "res://x",
        "proposed_at": "2026-01-01T00:00:01Z",
        "reason": "Because.",
    }
    defaults.update(kwargs)
    return ActionProposal(**defaults)


def make_decision(**kwargs):
    defaults = {
        "decision_id": "decision-001",
        "action_id": "action-001",
        "run_id": "run-001",
        "result": DecisionResult.allow,
        "policy_name": "pol-v1",
        "reason": "Allowed.",
        "decided_at": "2026-01-01T00:00:02Z",
        "deterministic_fingerprint": "fp-001",
        "trace_id": None,
    }
    defaults.update(kwargs)
    return PolicyDecision(**defaults)


def make_trace(**kwargs):
    defaults = {
        "trace_id": "trace-001",
        "run_id": "run-001",
        "action_id": "action-001",
        "evaluated_at": "2026-01-01T00:00:02Z",
        "final_result": DecisionResult.allow,
        "deterministic_fingerprint": "fp-001",
    }
    defaults.update(kwargs)
    return PolicyEvaluationTrace(**defaults)


def errors(report):
    return [i for i in report.issues if i.severity == ValidationSeverity.error]


def warnings(report):
    return [i for i in report.issues if i.severity == ValidationSeverity.warning]


def error_codes(report):
    return {i.code for i in errors(report)}


def warning_codes(report):
    return {i.code for i in warnings(report)}


class TestRequiredFieldErrors:
    def test_empty_bundle_id(self):
        bundle = make_bundle(bundle_id="")
        report = validate_replay_bundle(bundle)
        assert "E001" in error_codes(report)
        assert report.valid is False

    def test_empty_bundle_version(self):
        bundle = make_bundle(bundle_version="")
        report = validate_replay_bundle(bundle)
        assert "E002" in error_codes(report)

    def test_unknown_bundle_version_is_refused(self):
        for version in ("99.0-evil", "0.1.0", "0.2.0", "9.9.9"):
            report = validate_replay_bundle(make_bundle(bundle_version=version))
            assert "E002" in error_codes(report) and report.valid is False, version
        assert validate_replay_bundle(make_bundle(bundle_version="0.1")).valid is True

    def test_empty_run_id(self):
        bundle = make_bundle(run_id="")
        report = validate_replay_bundle(bundle)
        assert "E003" in error_codes(report)

    def test_empty_frame_id(self):
        bundle = make_bundle(frame=make_frame(frame_id=""))
        report = validate_replay_bundle(bundle)
        assert "E004" in error_codes(report)

    def test_empty_actor(self):
        bundle = make_bundle(frame=make_frame(actor=""))
        report = validate_replay_bundle(bundle)
        assert "E005" in error_codes(report)

    def test_empty_policy_version(self):
        bundle = make_bundle(frame=make_frame(policy_version=""))
        report = validate_replay_bundle(bundle)
        assert "E006" in error_codes(report)


class TestRunIdMismatch:
    def test_action_run_id_mismatch(self):
        ap = make_proposal(run_id="wrong-run")
        bundle = make_bundle(action_proposals=[ap])
        report = validate_replay_bundle(bundle)
        assert "E007" in error_codes(report)

    def test_decision_run_id_mismatch(self):
        ap = make_proposal()
        pd = make_decision(run_id="wrong-run")
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd])
        report = validate_replay_bundle(bundle)
        assert "E008" in error_codes(report)


class TestUnknownActionReferences:
    def test_decision_unknown_action(self):
        ap = make_proposal()
        pd = make_decision(action_id="nonexistent")
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd])
        report = validate_replay_bundle(bundle)
        assert "E009" in error_codes(report)

    def test_blocked_action_unknown_action(self):
        ap = make_proposal()
        pd = make_decision(result=DecisionResult.block, action_id="action-001")
        ba = BlockedAction(
            blocked_id="blocked-001",
            action_id="nonexistent",
            run_id="run-001",
            reason="Blocked.",
            policy_name="pol-v1",
            blocked_at="2026-01-01T00:00:03Z",
        )
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd], blocked_actions=[ba])
        report = validate_replay_bundle(bundle)
        assert "E011" in error_codes(report)

    def test_reliance_unknown_action(self):
        ap = make_proposal()
        rr = RelianceRecord(
            reliance_id="rel-001",
            run_id="run-001",
            source_name="db",
            source_type="database",
            scope="all",
            referenced_action_id="nonexistent",
            created_at="2026-01-01T00:00:01Z",
        )
        bundle = make_bundle(action_proposals=[ap], reliance_records=[rr])
        report = validate_replay_bundle(bundle)
        assert "E015" in error_codes(report)

    def test_trace_unknown_action(self):
        ap = make_proposal()
        trace = make_trace(action_id="nonexistent")
        bundle = make_bundle(action_proposals=[ap], policy_traces=[trace])
        report = validate_replay_bundle(bundle)
        assert "E017" in error_codes(report)


class TestBlockedActionConsistency:
    def test_blocked_action_without_block_decision(self):
        ap = make_proposal()
        pd = make_decision(result=DecisionResult.allow)
        ba = BlockedAction(
            blocked_id="blocked-001",
            action_id="action-001",
            run_id="run-001",
            reason="Blocked.",
            policy_name="pol-v1",
            blocked_at="2026-01-01T00:00:03Z",
        )
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd], blocked_actions=[ba])
        report = validate_replay_bundle(bundle)
        assert "E012" in error_codes(report)


class TestTraceConsistency:
    def test_decision_trace_id_unknown(self):
        ap = make_proposal()
        pd = make_decision(trace_id="nonexistent-trace")
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd])
        report = validate_replay_bundle(bundle)
        assert "E018" in error_codes(report)

    def test_trace_fingerprint_mismatch(self):
        ap = make_proposal()
        trace = make_trace(deterministic_fingerprint="fp-DIFFERENT")
        pd = make_decision(trace_id="trace-001", deterministic_fingerprint="fp-001")
        bundle = make_bundle(
            action_proposals=[ap],
            policy_decisions=[pd],
            policy_traces=[trace],
        )
        report = validate_replay_bundle(bundle)
        assert "E019" in error_codes(report)

    def test_trace_result_mismatch(self):
        ap = make_proposal()
        trace = make_trace(final_result=DecisionResult.block, deterministic_fingerprint="fp-001")
        pd = make_decision(
            trace_id="trace-001",
            result=DecisionResult.allow,
            deterministic_fingerprint="fp-001",
        )
        bundle = make_bundle(
            action_proposals=[ap],
            policy_decisions=[pd],
            policy_traces=[trace],
        )
        report = validate_replay_bundle(bundle)
        assert "E020" in error_codes(report)


class TestSignatureValidation:
    def test_signed_metadata_missing_algorithm(self):
        sig = SignatureMetadata(signed=True, signature="abc123")
        bundle = make_bundle(signature_metadata=sig)
        report = validate_replay_bundle(bundle)
        assert "E022" in error_codes(report)

    def test_signed_metadata_missing_signature(self):
        sig = SignatureMetadata(signed=True, signature_algorithm="HMAC-SHA256")
        bundle = make_bundle(signature_metadata=sig)
        report = validate_replay_bundle(bundle)
        assert "E023" in error_codes(report)


class TestRedactionValidation:
    def test_redacted_metadata_missing_redacted_at(self):
        rm = RedactionMetadata(redacted=True, redacted_fields=["payload"])
        bundle = make_bundle(redaction_metadata=rm)
        report = validate_replay_bundle(bundle)
        assert "E024" in error_codes(report)

    def test_redacted_metadata_empty_redacted_fields(self):
        rm = RedactionMetadata(redacted=True, redacted_at="2026-01-01T00:00:00Z")
        bundle = make_bundle(redaction_metadata=rm)
        report = validate_replay_bundle(bundle)
        assert "E025" in error_codes(report)


class TestWarnings:
    def test_no_action_proposals_warning(self):
        bundle = make_bundle()
        report = validate_replay_bundle(bundle)
        assert "W001" in warning_codes(report)

    def test_no_policy_decisions_warning(self):
        bundle = make_bundle()
        report = validate_replay_bundle(bundle)
        assert "W002" in warning_codes(report)

    def test_no_policy_traces_warning(self):
        bundle = make_bundle()
        report = validate_replay_bundle(bundle)
        assert "W003" in warning_codes(report)

    def test_decision_no_trace_id_warning(self):
        ap = make_proposal()
        pd = make_decision(trace_id=None)
        bundle = make_bundle(action_proposals=[ap], policy_decisions=[pd])
        report = validate_replay_bundle(bundle)
        assert "W009" in warning_codes(report)

    def test_complete_missing_output_warning(self):
        bundle = make_bundle(final_output=None)
        report = validate_replay_bundle(bundle)
        assert "W010" in warning_codes(report)

    def test_warnings_do_not_make_invalid(self):
        bundle = make_bundle()
        report = validate_replay_bundle(bundle)
        # Warnings present but no errors
        assert all(i.severity == ValidationSeverity.warning for i in report.issues)
        assert report.valid is True

    def test_errors_make_invalid(self):
        bundle = make_bundle(bundle_id="")
        report = validate_replay_bundle(bundle)
        assert report.valid is False
