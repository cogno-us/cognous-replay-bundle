"""Redaction helpers for Agent Replay Bundle."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import (
    AgentReplayBundle,
    BundleStatus,
)


def redact_replay_bundle(
    bundle: AgentReplayBundle,
    *,
    redact_payloads: bool = True,
    redact_targets: bool = False,
    redact_final_output: bool = False,
    redact_reasons: bool = False,
    redact_task: bool = False,
    redact_scope: bool = False,
    clear_signature_metadata: bool = False,
    replacement: str = "[REDACTED]",
    redaction_policy: str | None = None,
) -> AgentReplayBundle:
    """Return a redacted deep copy of the bundle.

    The original bundle is not mutated.  Identifiers, timestamps, decision
    results, policy names, deterministic fingerprints, and cross-object
    references are always preserved.

    Args:
        bundle: The bundle to redact.
        redact_payloads: Replace action payload dicts with ``{"redacted": true}``.
        redact_targets: Replace action target strings with *replacement*.
        redact_final_output: Replace ``final_output`` with *replacement*.
        redact_reasons: Redact ``reason`` fields on ActionProposals,
            PolicyDecisions, PolicyRuleEvaluations, and BlockedActions.
        redact_task: Replace the run frame's ``task`` text with *replacement*.
        redact_scope: Replace ``RelianceRecord.scope`` with *replacement* and each ``AuthorityRecord.scope`` list with a
            one-item list holding *replacement*.
        clear_signature_metadata: Drop the embedded ``signature_metadata``: it describes a signature over the content before
            redaction and no longer matches.
        replacement: The placeholder string used when replacing text values.
        redaction_policy: Optional name of the redaction policy being applied.

    Returns:
        A new AgentReplayBundle with redaction applied and
        ``RedactionMetadata`` populated.
    """
    data = bundle.model_dump(mode="json")
    redacted_fields: list[str] = []

    # Redact action proposals
    for i, ap in enumerate(data.get("action_proposals", [])):
        if redact_payloads:
            ap["payload"] = {"redacted": True}
            redacted_fields.append(f"action_proposals[{i}].payload")
        if redact_targets:
            ap["target"] = replacement
            redacted_fields.append(f"action_proposals[{i}].target")
        if redact_reasons and ap.get("reason") is not None:
            ap["reason"] = replacement
            redacted_fields.append(f"action_proposals[{i}].reason")

    # Redact policy decisions
    if redact_reasons:
        for i, pd in enumerate(data.get("policy_decisions", [])):
            pd["reason"] = replacement
            redacted_fields.append(f"policy_decisions[{i}].reason")

    # Redact policy traces — rule evaluation reasons
    if redact_reasons:
        for i, pt in enumerate(data.get("policy_traces", [])):
            for j, rule in enumerate(pt.get("rules_evaluated", [])):
                rule["reason"] = replacement
                redacted_fields.append(f"policy_traces[{i}].rules_evaluated[{j}].reason")

    # Redact blocked actions
    if redact_reasons:
        for i, ba in enumerate(data.get("blocked_actions", [])):
            ba["reason"] = replacement
            redacted_fields.append(f"blocked_actions[{i}].reason")

    # Redact the task text of the run frame
    if redact_task:
        data["frame"]["task"] = replacement
        redacted_fields.append("frame.task")

    # Redact scope descriptions
    if redact_scope:
        for i, rr in enumerate(data.get("reliance_records", [])):
            rr["scope"] = replacement
            redacted_fields.append(f"reliance_records[{i}].scope")
        for i, ar in enumerate(data.get("authority_records", [])):
            ar["scope"] = [replacement]
            redacted_fields.append(f"authority_records[{i}].scope")

    # Drop embedded signature metadata that describes the pre-redaction content
    if clear_signature_metadata and data.get("signature_metadata") is not None:
        data["signature_metadata"] = None
        redacted_fields.append("signature_metadata")

    # Redact final output
    if redact_final_output and data.get("final_output") is not None:
        data["final_output"] = replacement
        redacted_fields.append("final_output")

    # Update status
    data["status"] = BundleStatus.redacted.value

    # Build or update redaction metadata
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = data.get("redaction_metadata") or {}
    existing_fields = existing.get("redacted_fields", []) if existing else []
    merged_fields = list(dict.fromkeys(existing_fields + redacted_fields))

    data["redaction_metadata"] = {
        "redacted": True,
        "redacted_at": now_iso,
        "redacted_fields": merged_fields,
        "redaction_policy": redaction_policy,
        "replacement": replacement,
        "notes": existing.get("notes") if existing else None,
    }

    return AgentReplayBundle.model_validate(data)
