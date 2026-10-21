"""Semantic validator for Agent Replay Bundle."""

from __future__ import annotations

from .models import (
    AgentReplayBundle,
    BundleStatus,
    DecisionResult,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)

_SENSITIVE_KEYS = {
    "email",
    "phone",
    "ssn",
    "account_number",
    "customer_id",
    "address",
    "token",
    "secret",
    "password",
}


#: Versions of the 0.1 replay-bundle format this validator checks (docs/bundle_format.md: default "0.1"). The 0.2.0
#: reconstruction bundle is a different model with its own loader and is not validated here.
SUPPORTED_BUNDLE_VERSIONS = frozenset({"0.1"})


def _error(code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(severity=ValidationSeverity.error, code=code, message=message, path=path)


def _warning(code: str, message: str, path: str | None = None) -> ValidationIssue:
    return ValidationIssue(severity=ValidationSeverity.warning, code=code, message=message, path=path)


def validate_replay_bundle(bundle: AgentReplayBundle) -> ValidationReport:
    """Validate an AgentReplayBundle and return a ValidationReport.

    Args:
        bundle: The bundle to validate.

    Returns:
        A ValidationReport describing errors and warnings found.
    """
    issues: list[ValidationIssue] = []

    # -------------------------------------------------------------------------
    # Error rules
    # -------------------------------------------------------------------------

    # 1. bundle_id must be non-empty
    if not bundle.bundle_id:
        issues.append(_error("E001", "bundle_id must be non-empty.", "bundle_id"))

    # 2. bundle_version must be non-empty and one of the supported versions
    if not bundle.bundle_version:
        issues.append(_error("E002", "bundle_version must be non-empty.", "bundle_version"))
    elif bundle.bundle_version not in SUPPORTED_BUNDLE_VERSIONS:
        issues.append(_error(
            "E002",
            f"bundle_version {bundle.bundle_version!r} is not a supported version "
            f"(supported: {', '.join(sorted(SUPPORTED_BUNDLE_VERSIONS))}).",
            "bundle_version",
        ))

    # 3. run_id must be non-empty
    if not bundle.run_id:
        issues.append(_error("E003", "run_id must be non-empty.", "run_id"))

    # 4. frame.frame_id must be non-empty
    if not bundle.frame.frame_id:
        issues.append(_error("E004", "frame.frame_id must be non-empty.", "frame.frame_id"))

    # 5. frame.actor must be non-empty
    if not bundle.frame.actor:
        issues.append(_error("E005", "frame.actor must be non-empty.", "frame.actor"))

    # 6. frame.policy_version must be non-empty
    if not bundle.frame.policy_version:
        issues.append(_error("E006", "frame.policy_version must be non-empty.", "frame.policy_version"))

    proposal_ids = {ap.action_id for ap in bundle.action_proposals}
    trace_ids = {pt.trace_id: pt for pt in bundle.policy_traces}

    # 7. every ActionProposal.run_id must equal bundle.run_id
    for i, ap in enumerate(bundle.action_proposals):
        if ap.run_id != bundle.run_id:
            issues.append(_error("E007", f"ActionProposal run_id mismatch: '{ap.run_id}' != '{bundle.run_id}'.", f"action_proposals[{i}].run_id"))

    # 8. every PolicyDecision.run_id must equal bundle.run_id
    # 9. every PolicyDecision.action_id must reference an existing ActionProposal.action_id
    for i, pd in enumerate(bundle.policy_decisions):
        if pd.run_id != bundle.run_id:
            issues.append(_error("E008", f"PolicyDecision run_id mismatch: '{pd.run_id}' != '{bundle.run_id}'.", f"policy_decisions[{i}].run_id"))
        if pd.action_id not in proposal_ids:
            issues.append(_error("E009", f"PolicyDecision references unknown action_id '{pd.action_id}'.", f"policy_decisions[{i}].action_id"))

    # 10. every BlockedAction.run_id must equal bundle.run_id
    # 11. every BlockedAction.action_id must reference an existing ActionProposal.action_id
    # 12. every BlockedAction must correspond to at least one PolicyDecision for the same action_id with result "block"
    block_decision_action_ids = {
        pd.action_id for pd in bundle.policy_decisions if pd.result == DecisionResult.block
    }
    for i, ba in enumerate(bundle.blocked_actions):
        if ba.run_id != bundle.run_id:
            issues.append(_error("E010", f"BlockedAction run_id mismatch: '{ba.run_id}' != '{bundle.run_id}'.", f"blocked_actions[{i}].run_id"))
        if ba.action_id not in proposal_ids:
            issues.append(_error("E011", f"BlockedAction references unknown action_id '{ba.action_id}'.", f"blocked_actions[{i}].action_id"))
        if ba.action_id not in block_decision_action_ids:
            issues.append(_error("E012", f"BlockedAction for action_id '{ba.action_id}' has no corresponding PolicyDecision with result 'block'.", f"blocked_actions[{i}].action_id"))

    # 13. every AuthorityRecord.run_id must equal bundle.run_id
    for i, ar in enumerate(bundle.authority_records):
        if ar.run_id != bundle.run_id:
            issues.append(_error("E013", f"AuthorityRecord run_id mismatch: '{ar.run_id}' != '{bundle.run_id}'.", f"authority_records[{i}].run_id"))

    # 14. every RelianceRecord.run_id must equal bundle.run_id
    # 15. every RelianceRecord.referenced_action_id, when present, must reference an existing ActionProposal
    for i, rr in enumerate(bundle.reliance_records):
        if rr.run_id != bundle.run_id:
            issues.append(_error("E014", f"RelianceRecord run_id mismatch: '{rr.run_id}' != '{bundle.run_id}'.", f"reliance_records[{i}].run_id"))
        if rr.referenced_action_id is not None and rr.referenced_action_id not in proposal_ids:
            issues.append(_error("E015", f"RelianceRecord references unknown action_id '{rr.referenced_action_id}'.", f"reliance_records[{i}].referenced_action_id"))

    # 16. every PolicyEvaluationTrace.run_id must equal bundle.run_id
    # 17. every PolicyEvaluationTrace.action_id must reference an existing ActionProposal
    for i, pt in enumerate(bundle.policy_traces):
        if pt.run_id != bundle.run_id:
            issues.append(_error("E016", f"PolicyEvaluationTrace run_id mismatch: '{pt.run_id}' != '{bundle.run_id}'.", f"policy_traces[{i}].run_id"))
        if pt.action_id not in proposal_ids:
            issues.append(_error("E017", f"PolicyEvaluationTrace references unknown action_id '{pt.action_id}'.", f"policy_traces[{i}].action_id"))

    # 18. every PolicyDecision.trace_id, when present, must reference an existing PolicyEvaluationTrace
    # 19. if trace_id present, trace fingerprint must match decision fingerprint
    # 20. if trace_id present, trace final_result must match decision result
    for i, pd in enumerate(bundle.policy_decisions):
        if pd.trace_id is not None:
            if pd.trace_id not in trace_ids:
                issues.append(_error("E018", f"PolicyDecision references unknown trace_id '{pd.trace_id}'.", f"policy_decisions[{i}].trace_id"))
            else:
                trace = trace_ids[pd.trace_id]
                if trace.deterministic_fingerprint != pd.deterministic_fingerprint:
                    issues.append(_error("E019", f"PolicyDecision deterministic_fingerprint '{pd.deterministic_fingerprint}' does not match trace '{trace.deterministic_fingerprint}'.", f"policy_decisions[{i}].deterministic_fingerprint"))
                if trace.final_result != pd.result:
                    issues.append(_error("E020", f"PolicyDecision result '{pd.result}' does not match trace final_result '{trace.final_result}'.", f"policy_decisions[{i}].result"))

    # 22. if signature_metadata.signed is true, signature_algorithm and signature must be present
    if bundle.signature_metadata is not None and bundle.signature_metadata.signed:
        if not bundle.signature_metadata.signature_algorithm:
            issues.append(_error("E022", "signature_metadata.signed is true but signature_algorithm is missing.", "signature_metadata.signature_algorithm"))
        if not bundle.signature_metadata.signature:
            issues.append(_error("E023", "signature_metadata.signed is true but signature is missing.", "signature_metadata.signature"))

    # 23. if redaction_metadata.redacted is true, redacted_at must be present and redacted_fields should not be empty
    if bundle.redaction_metadata is not None and bundle.redaction_metadata.redacted:
        if not bundle.redaction_metadata.redacted_at:
            issues.append(_error("E024", "redaction_metadata.redacted is true but redacted_at is missing.", "redaction_metadata.redacted_at"))
        if not bundle.redaction_metadata.redacted_fields:
            issues.append(_error("E025", "redaction_metadata.redacted is true but redacted_fields is empty.", "redaction_metadata.redacted_fields"))

    # -------------------------------------------------------------------------
    # Warning rules
    # -------------------------------------------------------------------------

    # W1. bundle has no action proposals
    if not bundle.action_proposals:
        issues.append(_warning("W001", "Bundle has no action proposals."))

    # W2. bundle has no policy decisions
    if not bundle.policy_decisions:
        issues.append(_warning("W002", "Bundle has no policy decisions."))

    # W3. bundle has no policy traces
    if not bundle.policy_traces:
        issues.append(_warning("W003", "Bundle has no policy evaluation traces."))

    # W4. bundle has no reliance records
    if not bundle.reliance_records:
        issues.append(_warning("W004", "Bundle has no reliance records."))

    # W5. bundle has no authority records
    if not bundle.authority_records:
        issues.append(_warning("W005", "Bundle has no authority records."))

    # W6. frame.allowed_tools is empty
    if not bundle.frame.allowed_tools:
        issues.append(_warning("W006", "frame.allowed_tools is empty.", "frame.allowed_tools"))

    # W7. frame.blocked_tools is empty
    if not bundle.frame.blocked_tools:
        issues.append(_warning("W007", "frame.blocked_tools is empty.", "frame.blocked_tools"))

    # W8. action has no reason
    for i, ap in enumerate(bundle.action_proposals):
        if ap.reason is None:
            issues.append(_warning("W008", f"ActionProposal '{ap.action_id}' has no reason.", f"action_proposals[{i}].reason"))

    # W9. policy decision has no trace_id
    for i, pd in enumerate(bundle.policy_decisions):
        if pd.trace_id is None:
            issues.append(_warning("W009", f"PolicyDecision '{pd.decision_id}' has no trace_id.", f"policy_decisions[{i}].trace_id"))

    # W10. bundle is complete but final_output is missing
    if bundle.status == BundleStatus.complete and bundle.final_output is None:
        issues.append(_warning("W010", "Bundle status is 'complete' but final_output is missing.", "final_output"))

    # W11. sensitive-looking payload keys but no redaction_metadata
    if bundle.redaction_metadata is None:
        for i, ap in enumerate(bundle.action_proposals):
            sensitive_found = _SENSITIVE_KEYS.intersection(str(k).lower() for k in ap.payload)
            if sensitive_found:
                issues.append(_warning("W011", f"ActionProposal '{ap.action_id}' payload contains potentially sensitive keys ({', '.join(sorted(sensitive_found))}) but redaction_metadata is not present.", f"action_proposals[{i}].payload"))

    # W12. signature_metadata is missing
    if bundle.signature_metadata is None:
        issues.append(_warning("W012", "signature_metadata is missing.", "signature_metadata"))

    # W13. embedded validation_report is stale or checked_id does not match bundle_id
    if bundle.validation_report is not None:
        if bundle.validation_report.checked_id != bundle.bundle_id:
            issues.append(_warning("W013", f"Embedded validation_report.checked_id '{bundle.validation_report.checked_id}' does not match bundle_id '{bundle.bundle_id}'.", "validation_report.checked_id"))

    has_errors = any(issue.severity == ValidationSeverity.error for issue in issues)
    return ValidationReport(
        valid=not has_errors,
        checked_object_type="AgentReplayBundle",
        checked_id=bundle.bundle_id,
        issues=issues,
    )
