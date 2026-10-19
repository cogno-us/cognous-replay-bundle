"""Revision-pinned producer import adapters."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from .instants import parse_instant
from .programme2_profiles import freshness_on
from .reconstruction import (
    CANONICAL_JSON_PROFILE,
    CommitmentRecord,
    ImportFinding,
    ImportReport,
    ProducerProfile,
    ReconstructionBundle,
    RecordLink,
    SourceRecord,
    canonical_bytes,
)

CONTROL_PLANE_REVISION = "283500652d47a692fb0b99a1172a6d5faffbd9a7"
LEGACY_MOLTBOT_SAFE_REVISION = "6b0ba1185bcd390f71df947dda349415e4105f5f"
MOLTBOT_SAFE_REVISION = "1d308faf664c504b6e310db3c7a310153ef7b067"  # accepted producer-profile implementation
MOLTBOT_PRODUCER_PROFILE_ID = "urn:cognous:profiles:moltbot-safe-executor-producer"
MOLTBOT_PRODUCER_PROFILE_VERSION = "1.0.0"
MANIFEST_REVISION = "46c950bed37fe3812000895430bc0312d29e37ce"
ALVORADA_REVISION = "fb3d97938969a89e149e8ff8db2756091d1233fc"

LEGACY_PROFILE = "control-plane-legacy-replay@28350065"
BOUNDED_PROFILE = "control-plane-bounded-run@28350065"
LEGACY_MOLTBOT_PROFILE = "moltbot-safe-envelope-0.2.0@6b0ba118"
MOLTBOT_PROFILE = "moltbot-safe-executor-producer-1.0.0@1d308faf"


CONTROL_PLANE_V2_REVISION = "2ea9528eeb87e14ff10f05de06473122b9df540f"
CONTROL_PLANE_V2_PERSISTENCE_REVISION = "248d899634d9db3518e831bc7ab568a48733f825"
CONTROL_PLANE_V2_REVISIONS = (
    CONTROL_PLANE_V2_REVISION,
    CONTROL_PLANE_V2_PERSISTENCE_REVISION,
)
CONTROL_PLANE_MERGED_REVISION = "d3dadee70bd319812b207389ab1e0f6efe511916"
MOLTBOT_MERGED_REVISION = "c3c3ee7188b9367cf70b08074b9c40a5c70c94ac"
BOUNDED_MERGED_PROFILE = "control-plane-bounded-run@d3dadee7"
MOLTBOT_MERGED_PROFILE = "moltbot-safe-executor-producer-2.0.0@c3c3ee71"
CONTROL_PLANE_REFUSAL_REVISION = "c7f122ba3a6e39f9268a7163c99be3ee514cd97e"
MOLTBOT_REFUSAL_REVISION = "309e194c1b0a3de23e11e20133e6eaf88875e48a"
BOUNDED_REFUSAL_PROFILE = "control-plane-bounded-refusal@c7f122ba"
MOLTBOT_REFUSAL_PROFILE = "moltbot-safe-executor-producer-2.0.0@309e194c"
CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION = "2a17b2ba147462a592d9b1882aad09d8a3eb7904"
MOLTBOT_RUNTIME_AUTHORITY_REVISION = "a9a4f75a9a880ba0ae2c3b5a01fcee0ae904e127"
BOUNDED_RUNTIME_AUTHORITY_PROFILE = "control-plane-runtime-authority@2a17b2ba"
MOLTBOT_RUNTIME_AUTHORITY_PROFILE = "moltbot-safe-executor-producer-2.0.0@a9a4f75a"
# Separate exact producer generation after the runtime security repair.
CONTROL_PLANE_SECURITY_REVISION = "996baeb476c8745b1a58ddc968b9eecc6a39b76b"
MOLTBOT_SECURITY_REVISION = "fd6b76fa0e85feb5b67324114bf790d3a12fdaf1"
MANIFEST_SECURITY_REVISION = "e385f8c19b4444817a8b84b72ed6edbc37deb807"
BOUNDED_SECURITY_PROFILE = "control-plane-security-runtime@996baeb4"
MOLTBOT_SECURITY_PROFILE = "moltbot-safe-executor-producer-2.0.0@fd6b76fa"
# Separate exact producer generation after the F5b security repairs. The
# 996baeb4/fd6b76fa generation above stays accepted for retained evidence.
CONTROL_PLANE_F5B_REVISION = "a34c3dc26f84a767a55f9d5c89dc0b53e63fefa5"
MOLTBOT_F5B_REVISION = "4a83b175d2ef0e65a7ee22a0513bb94a5fdf3a6f"
MANIFEST_F5B_REVISION = "2c36bcd0b620dbfe7ad924bc7196a3f0c04c5c5e"
BOUNDED_F5B_PROFILE = "control-plane-security-runtime@a34c3dc2"
MOLTBOT_F5B_PROFILE = "moltbot-safe-executor-producer-2.0.0@4a83b175"
# Control Plane revisions whose bounded output uses the security-runtime semantics.
# P4 generation (alpha decoupling, P4): the producers after the execution-attempt lifecycle contract work
# (0.1.0-draft, not frozen). Same Control Plane / runtime semantics as F5b plus the contract's export layout, but a
# distinct exact revision tuple, added beside (never replacing) F5b so retained F5b evidence stays accepted.
# These constants are alpha scaffolding: they are removed with the other hard pins at end-of-alpha (P5).
CONTROL_PLANE_P4_REVISION = "26a7e6594eb535827ccc248cbca36a7d119d613b"
MOLTBOT_P4_REVISION = "3024ef6e6ecf7da22e5f4fdf90d873f93b2a55c9"
MANIFEST_P4_REVISION = MANIFEST_F5B_REVISION
BOUNDED_P4_PROFILE = "control-plane-security-runtime@26a7e659"
MOLTBOT_P4_PROFILE = "moltbot-safe-executor-producer-2.0.0@3024ef6e"
# Programme-2 generation (opt-in profiles): Control Plane 6093aca7 (3cd17ead plus the scan-fix stream: strict writers, redaction, freshness hardening; main after operation identity N1, rule revision N2, freshness
# N3, the N5 witness/holder inventory, merge-record/reversibility/dedupe-ttl N4, the 0.1/0.2 reason registry split, strict JSON J3,
# the opt-in terminal-revocation profile and strict instant parsing). It replaces the earlier ties to 3755c71a and 128eaa5e (this
# generation is one exact revision, never a range). Same import semantics as P4 for a
# profile-off run (byte-identical records), plus the members of the opt-in profiles when a run carries them (see
# programme2_profiles.py). The executor pairing is the runtime 62a5cc15 (11de097c plus profile composition, amount exactness, producer export and closeout identity hardening), with the action manifest f9ae8527: an executor
# export of any other runtime revision is refused as an unsupported combination. Alpha scaffolding like the other pins; removed with
# them at end-of-alpha (P5).
CONTROL_PLANE_P2_REVISION = "6093aca7b945698e89c0d8ac7c75306375e1a298"
MOLTBOT_P2_REVISION = "62a5cc156ecb439b4103b757fd265f276bb30374"
MANIFEST_P2_REVISION = "f9ae8527326c07e3177b5f003e626b23758be3d0"
BOUNDED_P2_PROFILE = "control-plane-programme2-profiles@6093aca7"
MOLTBOT_P2_PROFILE = "moltbot-safe-executor-producer-2.0.0@62a5cc15"
PROGRAMME2_CP_REVISIONS = frozenset({CONTROL_PLANE_P2_REVISION})
SECURITY_RUNTIME_CP_REVISIONS = frozenset({CONTROL_PLANE_SECURITY_REVISION, CONTROL_PLANE_F5B_REVISION, CONTROL_PLANE_P4_REVISION, CONTROL_PLANE_P2_REVISION})
SECURITY_RUNTIME_BOUNDED_PROFILES = frozenset({BOUNDED_SECURITY_PROFILE, BOUNDED_F5B_PROFILE, BOUNDED_P4_PROFILE, BOUNDED_P2_PROFILE})
CONTROL_PLANE_SUPPORTED_V2_REVISIONS = (*CONTROL_PLANE_V2_REVISIONS, CONTROL_PLANE_MERGED_REVISION, CONTROL_PLANE_REFUSAL_REVISION, CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, CONTROL_PLANE_SECURITY_REVISION, CONTROL_PLANE_F5B_REVISION, CONTROL_PLANE_P4_REVISION, CONTROL_PLANE_P2_REVISION)
MOLTBOT_V2_REVISION = "177354e959cc78c59c1a776f018cfbfbf28c927b"
BOUNDED_V2_PROFILE = "control-plane-bounded-run@2ea9528e"
BOUNDED_V2_PERSISTENCE_PROFILE = "control-plane-bounded-run@248d8996"
MOLTBOT_V2_PROFILE = "moltbot-safe-executor-producer-2.0.0@177354e9"
# Every 2.0 executor profile fails closed on a dangling/ambiguous explicit attempt reference.
STRICT_ACK_PROFILES = frozenset({MOLTBOT_V2_PROFILE, MOLTBOT_MERGED_PROFILE, MOLTBOT_REFUSAL_PROFILE,
                                 MOLTBOT_RUNTIME_AUTHORITY_PROFILE, MOLTBOT_SECURITY_PROFILE,
                                 MOLTBOT_F5B_PROFILE, MOLTBOT_P4_PROFILE, MOLTBOT_P2_PROFILE})
PRODUCER_COMPATIBILITY = {
    "1.0.0": (MOLTBOT_SAFE_REVISION, CONTROL_PLANE_REVISION, MOLTBOT_PROFILE),
    "2.0.0": (MOLTBOT_V2_REVISION, CONTROL_PLANE_V2_REVISION, MOLTBOT_V2_PROFILE),
}


class ImportContractError(ValueError):
    """Producer data violates the pinned import contract.

    ``code`` is the refusal code of the ODES ``execution-attempt-lifecycle`` contract (for example
    ``undeclared_member`` or ``recovery_retry_eligible``) when the refusal is one the contract names, else ``None``.
    The message text is unchanged by the code and stays the human-readable detail.
    """

    def __init__(self, message: str = "", code: str | None = None):
        super().__init__(message)
        self.code = code


def _sha256(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ImportContractError(f"{path} must be an object")
    return value


def _record(profile: str, kind: str, seq: int, path: str, data: dict[str, Any],
            *, ids: dict[str, Any] | None = None, at: str | None = None) -> SourceRecord:
    return SourceRecord(
        record_id=f"{profile}:{kind}:{seq}",
        producer_profile_id=profile,
        record_type=kind,
        source_sequence=seq,
        source_path=path,
        recorded_at=at,
        identifiers={k: str(v) for k, v in (ids or {}).items() if v not in (None, "")},
        data=data,
    )


def _unique_or_same(seen: dict[str, dict[str, Any]], key: str, value: dict[str, Any],
                    label: str, code: str | None = None) -> None:
    old = seen.get(key)
    if old is None:
        seen[key] = value
    elif old != value:
        raise ImportContractError(f"conflicting content under immutable {label} {key}", code)


def _require_equal(actual: Any, expected: Any, path: str, code: str | None = None) -> None:
    if actual != expected:
        raise ImportContractError(f"{path} conflicts with committed operation", code)


def _proposal_commitment(proposal: dict[str, Any]) -> str:
    return _sha256(proposal)


def _validate_proposal_binding(proposal: dict[str, Any], binding: dict[str, Any], path: str) -> None:
    expected_commitment = _proposal_commitment(proposal)
    _require_equal(binding.get("proposal_commitment"), expected_commitment, path + ".proposal_commitment")
    fields = (
        "manifest_id", "manifest_version", "manifest_digest", "actor", "principal",
        "action_id", "adapter_id", "target", "payload_commitment",
        "requested_permissions", "amount", "unit", "effects", "requirement_id",
    )
    for field in fields:
        actual = binding.get(field)
        expected = proposal.get(field)
        if field == "requested_permissions" and isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            actual, expected = list(actual), list(expected)
        _require_equal(actual, expected, path + "." + field)


def _validate_envelope_chain(
    op: dict[str, Any], proposal: dict[str, Any], binding: dict[str, Any]
) -> None:
    proposal_fields = (
        "actor", "principal", "manifest_id", "manifest_version", "manifest_digest",
        "action_id", "adapter_id", "target", "payload", "payload_commitment",
        "requested_permissions", "amount", "unit", "effects", "requirement_id",
    )
    for field in proposal_fields:
        actual = op.get(field)
        expected = proposal.get(field)
        if field == "requested_permissions" and isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            actual, expected = list(actual), list(expected)
        _require_equal(actual, expected, "execution_envelope.operation." + field)
    _require_equal(
        op.get("authority_context_id"), proposal.get("authority_context_ref"),
        "execution_envelope.operation.authority_context_id(profile_ref)",
    )
    _require_equal(
        op.get("proposal_commitment"), _proposal_commitment(proposal),
        "execution_envelope.operation.proposal_commitment",
    )
    for field in ("grant_id", "grant_revision", "effective_max_effects"):
        _require_equal(op.get(field), binding.get(field), "execution_envelope.operation." + field)


def _decode_payload_json(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, str):
        raise ImportContractError(f"{path} must be canonical JSON text")
    from .ingress import InputBoundsError, check_depth
    try:
        check_depth(value, MAX_RECORD_DEPTH)  # the text is decoded here, after the in-memory record walk has passed
        decoded = __import__("json").loads(value)
    except InputBoundsError as exc:
        raise ImportContractError(f"{path} exceeds the nesting limit", code="input_too_deep") from exc
    except (TypeError, ValueError, RecursionError) as exc:
        raise ImportContractError(f"{path} is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ImportContractError(f"{path} must decode to an object")
    return decoded


# Route B (atomic local executor) reports a post-commit failure as result 'unknown' carrying a *recovery*
# observation: the destination's claim-reconciliation report, keyed by 'status' (not the Control Plane
# observation's 'state'). It is a recovery report, never validated Control Plane evidence.
RECOVERY_OBSERVATION_KEYS = {"status", "claim_state", "retry_eligible", "effect_id", "operation_digest", "reason",
                             "extensions"}
RECOVERY_OBSERVATION_STATUSES = {"applied", "partial", "hold", "unknown"}

# Closed enumerations and member sets of the ODES execution-attempt-lifecycle contract (0.1.0-draft). A value
# outside an enumeration is refused as ``unknown_enum_value`` and never coerced.
ATTEMPT_EVENT_STATUSES = frozenset({"attempted", "executed", "partial", "failed", "reconciled", "unknown", "denied"})
EXECUTION_RESULT_STATUSES = frozenset({"denied", "failed", "partial", "unknown", "executed", "observed", "reconciled"})
VALIDATED_OBSERVATION_STATES = frozenset({"absent", "applied", "partial", "unknown"})
CONTROL_PLANE_ATTEMPT_STATUSES = frozenset({"attempted", "acknowledged", "unknown", "failed", "partial"})
CONTROL_PLANE_TIME_SOURCES = frozenset({"unrecorded", "control_plane", "test_override"})
EXECUTOR_ATTEMPT_MEMBERS = frozenset({"attempt_id", "effect_id", "decision_id", "operation_digest", "created_at",
                                      "extensions"})
ATTEMPT_EVENT_MEMBERS = frozenset({"event_id", "attempt_id", "status", "error", "created_at", "extensions"})
CONTROL_PLANE_ATTEMPT_MEMBERS = frozenset({"attempt_id", "effect_id", "decision_id", "started_at", "time_source",
                                           "status", "acknowledgement", "error", "extensions"})
EXTENSION_NAME = re.compile(r"^x-[a-z0-9][a-z0-9._-]*(?!\n)$")  # the whole string, never "before a trailing line break" (the contract's own form)


def _is_recovery_observation(observation: object) -> bool:
    return isinstance(observation, dict) and "state" not in observation and "status" in observation


def _recovery_observed_state(observation: dict[str, Any]) -> str:
    status = observation.get("status")
    return status if status in {"applied", "partial"} else "unknown"


def _observation_kind(observation: object) -> str:
    """'none' (null or empty), 'validated' (has ``state``) or 'recovery' (no ``state``): the contract's shape rule."""
    if not observation:
        return "none"
    return "validated" if "state" in observation else "recovery"


def _claims_attempt(result: dict[str, Any]) -> bool:
    return bool(result.get("attempted") or result.get("acknowledged") or result.get("newly_executed")
                or result.get("attempt_id") is not None)


def _validate_recovery_observation(observation: dict[str, Any], result: dict[str, Any],
                                   effect_id: str, op: dict[str, Any]) -> None:
    path = "execution_result.observation"
    extra = sorted(set(observation) - RECOVERY_OBSERVATION_KEYS)
    if extra:
        raise ImportContractError(f"{path} recovery report has undeclared members: " + ",".join(extra),
                                  "undeclared_member")
    status = observation.get("status")
    if status not in RECOVERY_OBSERVATION_STATUSES:
        raise ImportContractError(f"{path}.status is not a recovery status", "unknown_enum_value")
    retry = observation.get("retry_eligible")
    if retry is not False:
        raise ImportContractError("unsupported retry eligibility",
                                  "recovery_retry_eligible" if retry is True else "schema_violation")
    if result.get("status") not in {"observed", "unknown"}:
        raise ImportContractError("a recovery report is only carried by results unknown or observed",
                                  "recovery_observation_status")
    for field in ("claim_state", "effect_id", "operation_digest") if status in {"applied", "partial"} else ():
        if field not in observation:
            raise ImportContractError(f"{path}.{field} is required for an {status} recovery report",
                                      "recovery_report_incomplete")
    if status not in {"applied", "partial"} and (not isinstance(observation.get("reason"), str)
                                                  or not observation["reason"]):
        raise ImportContractError(f"{path}.reason is required for a {status} recovery report",
                                  "recovery_report_incomplete")
    if result.get("status") == "observed":
        # Effect-free reconcile (no attempt is made): the report is the whole result.
        if _claims_attempt(result):
            raise ImportContractError("an effect-free reconcile result cannot claim an attempt, acknowledgement or new effect",
                                      "effect_free_reconcile_claims_attempt")
    if result.get("observed_state") != _recovery_observed_state(observation):
        raise ImportContractError("recovery report observed-state contradiction",
                                  "recovery_state_mismatch" if result.get("status") == "observed"
                                  else "unknown_state_mismatch")
    if "effect_id" in observation:
        _require_equal(observation["effect_id"], effect_id, path + ".effect_id", "result_binding_mismatch")
    if "operation_digest" in observation:
        _require_equal(observation["operation_digest"], _sha256(op), path + ".operation_digest")


def _validate_observation_content(observation: dict[str, Any], effect_id: str, op: dict[str, Any], path: str) -> None:
    _require_equal(observation.get("effect_id"), effect_id, path + ".effect_id",
                   "result_binding_mismatch" if path == "execution_result.observation" else None)
    state = observation.get("state")
    destination = observation.get("destination_state")
    if state in {"applied", "partial"}:
        if not isinstance(destination, dict):
            raise ImportContractError(f"{path}.destination_state must be an object")
        for field in ("effect_id", "grant_id", "target", "amount", "unit"):
            expected = effect_id if field == "effect_id" else op.get(field)
            _require_equal(destination.get(field), expected, path + ".destination_state." + field)
        _require_equal(destination.get("payload"), op.get("payload"), path + ".destination_state.payload")
        if "operation_digest" in destination:
            _require_equal(destination.get("operation_digest"), _sha256(op), path + ".destination_state.operation_digest")


def import_legacy_control_plane_replay(source: dict[str, Any]) -> ReconstructionBundle:
    """Import the legacy ReplayBundle at the pinned Control Plane revision.

    Confirmed mappings are replay_bundle_id -> source_bundle_id,
    actions -> action_proposal records, and decisions -> policy_decision records.
    The source format has no embedded format version, so compatibility is
    revision-pinned rather than inferred from shape.
    """
    source = _obj(source, "source")
    required = {
        "replay_bundle_id", "run_id", "generated_at", "frame", "actions", "decisions",
        "policy_traces", "authority_records", "reliance_records", "blocked_actions",
    }
    missing = sorted(required - set(source))
    if missing:
        raise ImportContractError("legacy ReplayBundle missing: " + ",".join(missing))

    profile = ProducerProfile(
        profile_id=LEGACY_PROFILE,
        producer="Cognous Agent Control Plane",
        repository="cogno-us/cognous-agent-control-plane",
        revision=CONTROL_PLANE_REVISION,
        format_name="ReplayBundle",
        format_version=None,
        notes="No embedded format version; adapter is pinned to producer revision.",
    )
    report = ImportReport(
        adapter_profile=LEGACY_PROFILE,
        source_revision=CONTROL_PLANE_REVISION,
        complete=True,
        field_mappings={
            "replay_bundle_id": "metadata.source_bundle_id",
            "actions": "records[action_proposal]",
            "decisions": "records[policy_decision]",
            "policy_traces": "records[policy_trace]",
            "authority_records": "records[authority_record]",
            "reliance_records": "records[reliance_record]",
            "blocked_actions": "records[blocked_action]",
        },
    )
    records: list[SourceRecord] = []
    seq = 0
    frame = _obj(source["frame"], "frame")
    records.append(_record(LEGACY_PROFILE, "run_frame", seq, "frame", frame,
                           ids={"run_id": source["run_id"], "frame_id": frame.get("frame_id")},
                           at=frame.get("created_at")))
    seq += 1

    specs = (
        ("actions", "action_proposal", "action_id", "proposed_at"),
        ("decisions", "policy_decision", "decision_id", "decided_at"),
        ("policy_traces", "policy_trace", "trace_id", "evaluated_at"),
        ("authority_records", "authority_record", "authority_id", "created_at"),
        ("reliance_records", "reliance_record", "reliance_id", "created_at"),
        ("blocked_actions", "blocked_action", "blocked_id", "blocked_at"),
    )
    for field, kind, id_field, time_field in specs:
        values = source[field]
        if not isinstance(values, list):
            raise ImportContractError(f"{field} must be an array")
        for i, raw in enumerate(values):
            raw = _obj(raw, f"{field}[{i}]")
            records.append(_record(
                LEGACY_PROFILE, kind, seq, f"{field}[{i}]", raw,
                ids={"run_id": raw.get("run_id", source["run_id"]),
                     id_field: raw.get(id_field), "action_id": raw.get("action_id")},
                at=raw.get(time_field),
            ))
            seq += 1

    if "final_output" in source:
        records.append(_record(
            LEGACY_PROFILE, "final_output", seq, "final_output",
            {"value": source.get("final_output")}, ids={"run_id": source["run_id"]},
        ))

    extras = sorted(set(source) - required - {"final_output"})
    for field in extras:
        report.complete = False
        report.findings.append(ImportFinding(
            code="L001", category="unmapped_field", severity="warning", path=field,
            message="Field is outside the pinned legacy producer contract.",
        ))

    return ReconstructionBundle(
        run_id=str(source["run_id"]),
        status="reconstruction_complete" if report.complete else "reconstruction_partial",
        producer_profiles=[profile],
        records=records,
        import_reports=[report],
        metadata={
            "source_bundle_id": source["replay_bundle_id"],
            "source_generated_at": source["generated_at"],
            "source_format_version": None,
        },
    )



MOLTBOT_EXPORT_MEMBERS = frozenset({
    "execution_envelope", "execution_result", "effects", "attempts", "attempt_events",
    "producer_profile", "repository", "provenance", "attempt_identity",
    "control_plane_attempts", "observations", "recovery_observations", "control_plane_evidence",
    "rejected_observations", "extensions",
})
MOLTBOT_EXECUTION_RESULT_MEMBERS = frozenset({
    "status", "decision_id", "effect_id", "attempt_id", "attempted", "acknowledged", "observed_state",
    "newly_executed", "observation", "error", "control_plane_evidence", "extensions",
})
MOLTBOT_PRODUCER_PROFILE_MEMBERS = frozenset({"profile_id", "profile_version", "execution_envelope_version"})
MOLTBOT_REPOSITORY_MEMBERS = frozenset({"repository", "revision", "revision_status"})


def _check_extensions(obj: dict[str, Any], label: str) -> None:
    """The reserved ``extensions`` member (ODES inter-component contracts): an object whose names all match the
    contract's ``x-`` form (``^x-[a-z0-9][a-z0-9._-]*$``).

    Extensions are carried, never interpreted: they stay inside the retained record (so they are digested with it)
    and carry no authority. Undeclared members anywhere else still reject."""
    if "extensions" not in obj:
        return
    ext = obj["extensions"]
    if not isinstance(ext, dict):
        raise ImportContractError(f"{label}.extensions must be an object", "schema_violation")
    bad = sorted(str(k) for k in ext if not (isinstance(k, str) and EXTENSION_NAME.match(k)))
    if bad:
        raise ImportContractError(f"{label}.extensions names must start with 'x-': " + ",".join(bad),
                                  "invalid_extension_key")


def _reject_unknown_members(obj: dict[str, Any], allowed: frozenset[str], label: str) -> None:
    """Unsupported fields in typed records reject rather than disappear
    (docs/runtime-authority-profile.md)."""
    unknown = sorted(str(k) for k in set(obj) - allowed)
    if unknown:
        raise ImportContractError(f"{label} has unsupported member(s): " + ",".join(unknown), "undeclared_member")


def _closed_enum(value: Any, allowed: frozenset[str], label: str) -> None:
    if not isinstance(value, str) or value not in allowed:
        raise ImportContractError(f"{label} is not a declared value: {value!r}", "unknown_enum_value")


def _require_members(obj: dict[str, Any], names: tuple[str, ...], label: str) -> None:
    for name in names:
        if name not in obj:
            raise ImportContractError(f"{label}.{name} is required", "schema_violation")


def _validate_export_structure(source: dict[str, Any], result: dict[str, Any]) -> None:
    """Structure half of the execution-attempt-lifecycle contract for a producer 2.0.0 export: closed member
    sets, closed enumerations, required members and the ``x-`` extension namespace."""
    _check_extensions(source, "moltbot_export")
    for name, label in (("attempts", "moltbot.attempts"), ("attempt_events", "moltbot.attempt_events"),
                        ("control_plane_attempts", "moltbot.control_plane_attempts")):
        if name in source and not isinstance(source[name], list):
            raise ImportContractError(f"{name} must be an array", "schema_violation")
    for i, raw in enumerate(source["attempts"]):
        label = f"moltbot.attempts[{i}]"
        row = _obj(raw, label)
        _reject_unknown_members(row, EXECUTOR_ATTEMPT_MEMBERS, label)
        _check_extensions(row, label)
        _require_members(row, ("attempt_id", "effect_id", "decision_id"), label)
    for i, raw in enumerate(source["attempt_events"]):
        label = f"moltbot.attempt_events[{i}]"
        event = _obj(raw, label)
        _reject_unknown_members(event, ATTEMPT_EVENT_MEMBERS, label)
        _check_extensions(event, label)
        _require_members(event, ("event_id", "attempt_id", "status", "created_at"), label)
        _closed_enum(event["status"], ATTEMPT_EVENT_STATUSES, label + ".status")
    for i, raw in enumerate(source.get("control_plane_attempts") or []):
        _validate_control_plane_attempt_row(raw, f"moltbot.control_plane_attempts[{i}]")
    _reject_unknown_members(result, MOLTBOT_EXECUTION_RESULT_MEMBERS, "execution_result")
    _check_extensions(result, "execution_result")
    _require_members(result, ("status", "attempt_id", "observed_state", "observation"), "execution_result")
    _closed_enum(result["status"], EXECUTION_RESULT_STATUSES, "execution_result.status")
    observation = result["observation"]
    if observation is not None and not isinstance(observation, dict):
        raise ImportContractError("execution observation must be object or null", "schema_violation")
    if observation == {}:
        # Step B (owner decision 2026-10-17): the observation is null or a typed observation; `{}` is never valid.
        raise ImportContractError("execution observation must be null or a typed observation, not {}", "schema_violation")
    kind = _observation_kind(observation)
    if kind == "validated":
        _check_extensions(observation, "execution_result.observation")
        if not isinstance(observation.get("effect_id"), str) or not observation["effect_id"]:
            raise ImportContractError("execution_result.observation.effect_id is required", "schema_violation")
        _closed_enum(observation["state"], VALIDATED_OBSERVATION_STATES, "execution_result.observation.state")
    elif kind == "recovery":
        _check_extensions(observation, "execution_result.observation")
        _require_members(observation, ("status", "retry_eligible"), "execution_result.observation")
    for name in ("observations", "recovery_observations"):
        if name in source and not isinstance(source[name], list):
            raise ImportContractError(f"{name} must be an array", "schema_violation")
    for i, item in enumerate(source.get("observations") or []):
        # `observations` carries validated observations only (step B: the legacy layout that mirrored the recovery
        # report here is refused).
        if not isinstance(item, dict) or "state" not in item:
            raise ImportContractError(f"moltbot.observations[{i}] is not a validated observation (it has no state)",
                                      "schema_violation")
        _closed_enum(item["state"], VALIDATED_OBSERVATION_STATES, f"moltbot.observations[{i}].state")


_P2_ATTEMPT_MEMBERS = frozenset({"evaluated_at", "recorded_at"})  # freshness/0.1 clocks, programme-2 generation only


def _validate_control_plane_attempt_row(raw: Any, label: str, extra: frozenset[str] = frozenset()) -> None:
    row = _obj(raw, label)
    _reject_unknown_members(row, CONTROL_PLANE_ATTEMPT_MEMBERS | extra, label)
    _check_extensions(row, label)
    _require_members(row, ("attempt_id", "effect_id", "decision_id", "started_at", "status", "acknowledgement"), label)
    _closed_enum(row["status"], CONTROL_PLANE_ATTEMPT_STATUSES, label + ".status")
    if "time_source" in row:
        _closed_enum(row["time_source"], CONTROL_PLANE_TIME_SOURCES, label + ".time_source")
    if not isinstance(row["acknowledgement"], dict):
        raise ImportContractError(label + ".acknowledgement must be an object", "schema_violation")


def _moltbot_contract(source: dict[str, Any]) -> dict[str, Any]:
    declared = source.get("producer_profile")
    if declared is None:
        repository = source.get("repository")
        if repository is not None and _obj(repository, "legacy.repository").get("revision") != LEGACY_MOLTBOT_SAFE_REVISION:
            raise ImportContractError("unsupported legacy executor repository revision")
        return {
            "profile_id": LEGACY_MOLTBOT_PROFILE,
            "repository_revision": LEGACY_MOLTBOT_SAFE_REVISION,
            "interface_profile_id": None,
            "interface_profile_version": None,
            "provenance": {
                "mode": "legacy_revision_pinned",
                "source_asserted": {},
                "independently_established": [],
            },
            "legacy": True,
        }
    declared = _obj(declared, "moltbot_export.producer_profile")
    if declared.get("profile_id") != MOLTBOT_PRODUCER_PROFILE_ID:
        raise ImportContractError("unsupported Moltbot executor producer profile id")
    version = declared.get("profile_version")
    if not isinstance(version, str) or version not in PRODUCER_COMPATIBILITY:
        raise ImportContractError("unsupported Moltbot executor producer profile version")
    if declared.get("execution_envelope_version") != "0.2.0":
        raise ImportContractError("unsupported Moltbot producer execution envelope version")
    repository = _obj(source.get("repository"), "moltbot_export.repository")
    revision = repository.get("revision")
    supported_revision, cp_revision, profile = PRODUCER_COMPATIBILITY[version]
    compatible_cp_revisions = list(CONTROL_PLANE_V2_REVISIONS) if version == "2.0.0" else [cp_revision]
    # The merged pair is qualified for the unchanged bounded producer path only.
    # Preserve historical pairings; never accept a Cartesian product of revisions.
    if version == "2.0.0" and revision == MOLTBOT_MERGED_REVISION:
        supported_revision = MOLTBOT_MERGED_REVISION
        cp_revision = CONTROL_PLANE_MERGED_REVISION
        profile = MOLTBOT_MERGED_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_MERGED_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_REFUSAL_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_REFUSAL_REVISION, CONTROL_PLANE_REFUSAL_REVISION, MOLTBOT_REFUSAL_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_REFUSAL_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_RUNTIME_AUTHORITY_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_RUNTIME_AUTHORITY_REVISION, CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, MOLTBOT_RUNTIME_AUTHORITY_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_SECURITY_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_SECURITY_REVISION, CONTROL_PLANE_SECURITY_REVISION, MOLTBOT_SECURITY_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_SECURITY_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_F5B_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_F5B_REVISION, CONTROL_PLANE_F5B_REVISION, MOLTBOT_F5B_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_F5B_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_P4_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_P4_REVISION, CONTROL_PLANE_P4_REVISION, MOLTBOT_P4_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_P4_REVISION]
    if version == "2.0.0" and revision == MOLTBOT_P2_REVISION:
        supported_revision, cp_revision, profile = MOLTBOT_P2_REVISION, CONTROL_PLANE_P2_REVISION, MOLTBOT_P2_PROFILE
        compatible_cp_revisions = [CONTROL_PLANE_P2_REVISION]
    if revision != supported_revision:
        raise ImportContractError("unsupported Moltbot producer repository revision")
    if repository.get("revision_status") not in {"source_asserted", "unavailable"}:
        raise ImportContractError("unsupported Moltbot repository revision status")
    provenance = _obj(source.get("provenance"), "moltbot_export.provenance")
    asserted = provenance.get("source_asserted")
    independently = provenance.get("independently_established")
    if not isinstance(asserted, dict):
        raise ImportContractError("Moltbot source_asserted provenance must be an object")
    if not isinstance(independently, list):
        raise ImportContractError("Moltbot independently_established provenance must be an array")
    if asserted.get("producer_profile_id") != MOLTBOT_PRODUCER_PROFILE_ID:
        raise ImportContractError("Moltbot provenance profile id contradicts producer profile")
    if asserted.get("producer_profile_version") != version:
        raise ImportContractError("Moltbot provenance profile version contradicts producer profile")
    if asserted.get("repository_revision") != revision:
        raise ImportContractError("Moltbot provenance repository revision contradicts repository assertion")
    return {
        "profile_id": profile,
        "control_plane_revision": cp_revision,
        "compatible_control_plane_revisions": compatible_cp_revisions,
        "repository_revision": revision,
        "interface_profile_id": MOLTBOT_PRODUCER_PROFILE_ID,
        "interface_profile_version": version,
        "provenance": {
            "mode": "versioned_profile",
            "source_asserted": asserted,
            "independently_established": independently,
        },
        "legacy": False,
    }

MAX_RECORD_NODES = 2_000_000
MAX_RECORD_LIST_LENGTH = 100_000
MAX_RECORD_DEPTH = 128


def _require_unicode_text(text: str) -> None:
    """Text that cannot be encoded as UTF-8 (an unpaired surrogate code point) is refused, never evaluated
    (lifecycle contract input hardening: ``schema_violation``)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        raise ImportContractError("input text is not valid Unicode (unpaired surrogate)", "schema_violation") from None


def _check_record_bounds(value: Any) -> None:
    """Refuse oversized or too deeply nested in-memory input (the dict API has no byte budget).

    The limits are the same order as the CLI ingress bounds; the walk is iterative so deep input cannot overflow the stack.
    """
    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > MAX_RECORD_NODES:
            raise ImportContractError("input exceeds the node limit", code="input_too_large")
        if isinstance(item, str):
            _require_unicode_text(item)
        elif isinstance(item, (dict, list, tuple)):
            if depth > MAX_RECORD_DEPTH:
                raise ImportContractError("input exceeds the nesting limit", code="input_too_deep")
            if isinstance(item, dict):
                for key in item:
                    if isinstance(key, str):
                        _require_unicode_text(key)
                children = list(item.values())
            else:
                if len(item) > MAX_RECORD_LIST_LENGTH:
                    raise ImportContractError("input list exceeds the length limit", code="input_too_large")
                children = list(item)
            stack.extend((c, depth + 1) for c in children)


def import_bounded_workflow(
    control_plane_record: dict[str, Any],
    *,
    proposal: dict[str, Any] | None = None,
    moltbot_export: dict[str, Any] | None = None,
    control_plane_revision: str = CONTROL_PLANE_REVISION,
) -> ReconstructionBundle:
    """Import bounded Control Plane events and optional Moltbot destination evidence."""
    if control_plane_revision not in {CONTROL_PLANE_REVISION, *CONTROL_PLANE_SUPPORTED_V2_REVISIONS}:
        raise ImportContractError("unsupported Control Plane revision")
    _check_record_bounds(control_plane_record)
    _check_record_bounds(proposal)
    _check_record_bounds(moltbot_export)
    repaired = control_plane_revision in CONTROL_PLANE_SUPPORTED_V2_REVISIONS
    bounded_profile = {
        CONTROL_PLANE_V2_REVISION: BOUNDED_V2_PROFILE,
        CONTROL_PLANE_V2_PERSISTENCE_REVISION: BOUNDED_V2_PERSISTENCE_PROFILE,
        CONTROL_PLANE_MERGED_REVISION: BOUNDED_MERGED_PROFILE,
        CONTROL_PLANE_REFUSAL_REVISION: BOUNDED_REFUSAL_PROFILE,
        CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION: BOUNDED_RUNTIME_AUTHORITY_PROFILE,
        CONTROL_PLANE_SECURITY_REVISION: BOUNDED_SECURITY_PROFILE,
        CONTROL_PLANE_F5B_REVISION: BOUNDED_F5B_PROFILE,
        CONTROL_PLANE_P4_REVISION: BOUNDED_P4_PROFILE,
        CONTROL_PLANE_P2_REVISION: BOUNDED_P2_PROFILE,
    }.get(control_plane_revision, BOUNDED_PROFILE)
    if moltbot_export is not None:
        contract = _moltbot_contract(moltbot_export)
        expected_cps = contract.get(
            "compatible_control_plane_revisions",
            (contract.get("control_plane_revision", CONTROL_PLANE_REVISION),),
        )
        if control_plane_revision not in expected_cps:
            raise ImportContractError("unsupported executor/Control Plane revision combination")
        contract["control_plane_revision"] = control_plane_revision
    cp = _obj(control_plane_record, "control_plane_record")
    programme2 = control_plane_revision in PROGRAMME2_CP_REVISIONS
    if repaired:
        _validate_repaired_run(cp, profiles=programme2)
    required = {"run_id", "decisions", "attempts", "observations", "reconciliations"}
    missing = sorted(required - set(cp))
    if missing:
        raise ImportContractError("BoundedRunRecord missing: " + ",".join(missing))
    run_id = cp["run_id"]
    if not isinstance(run_id, str) or not run_id:
        raise ImportContractError("run_id must be a non-empty string")

    report = ImportReport(
        adapter_profile=bounded_profile,
        source_revision=control_plane_revision,
        complete=True,
        field_mappings={
            "decisions": "records[runtime_decision]",
            "attempts": "records[control_plane_attempt_transition]",
            "observations": "records[effect_observation]",
            "reconciliations": "records[reconciliation]",
        },
    )
    authority = control_plane_revision in {CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, *SECURITY_RUNTIME_CP_REVISIONS}
    extended = control_plane_revision in {CONTROL_PLANE_REFUSAL_REVISION, CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, *SECURITY_RUNTIME_CP_REVISIONS}
    if extended:
        from .refusal_evidence import EXTENDED, AUTHORITY_EXTENDED, validate_run
        EXTENDED = {**EXTENDED, **AUTHORITY_EXTENDED} if authority else EXTENDED
        if authority:
            cp = dict(cp)
            cp.setdefault("vocabulary_changes", [])
            if programme2:
                cp.setdefault("check_events", [])  # a run of check_lease_unavailable holds has no journal events (freshness/0.1)
        unfinished = validate_run(cp, proposal, runtime_authority=authority, profiles=programme2)
        if programme2:
            _validate_programme2_members(cp)
            from .programme2_profiles import PROFILE_LISTS
            report.field_mappings.update({field: "records[" + kind + "]" for field, kind in PROFILE_LISTS.items() if cp.get(field)})
        report.field_mappings.update({field: "records["+kind+"]" for field,kind in EXTENDED.items()})
        for check_id in unfinished:
            report.complete = False
            report.findings.append(ImportFinding(
                code="B006", category="value_state", severity="warning", path="check_events",
                message=f"Resolution journal check {check_id} is opened-only or interrupted; its authority evaluation did not complete.",
                value_state="unknown",
            ))
    if programme2:
        from .programme2_profiles import PROFILE_LISTS as _P2_LISTS
    for field in sorted(set(cp) - required - (set(EXTENDED) if extended else set()) - (set(_P2_LISTS) if programme2 else set())):
        report.complete = False
        report.findings.append(ImportFinding(
            code="B001", category="unmapped_field", severity="warning", path=field,
            message="Unknown top-level bounded record field.",
        ))

    records: list[SourceRecord] = []
    links: list[RecordLink] = []
    commitments: list[CommitmentRecord] = []
    seq = 0

    if proposal is not None:
        p = _obj(proposal, "proposal")
        if p.get("run_id") not in (None, run_id):
            raise ImportContractError("proposal.run_id conflicts with bounded run_id")
        prec = _record(
            bounded_profile, "runtime_proposal", seq, "proposal", p,
            ids={
                "run_id": p.get("run_id") or run_id,
                "correlation_id": p.get("correlation_id"),
                "action_id": p.get("action_id"),
                "manifest_id": p.get("manifest_id"),
                "authority_context_profile_ref": p.get("authority_context_ref"),
                "requirement_id": p.get("requirement_id"),
            },
        )
        records.append(prec)
        seq += 1
        pc = p.get("payload_commitment")
        if isinstance(pc, str) and pc:
            checked = _sha256(p.get("payload", {}))
            if checked != pc:
                raise ImportContractError("proposal payload commitment mismatch")
            commitments.append(CommitmentRecord(
                label="payload_commitment", value=pc, algorithm="SHA-256",
                canonicalization_profile=CANONICAL_JSON_PROFILE,
                source_record_id=prec.record_id, source_path="proposal.payload_commitment",
                verification_status="checked_match",
            ))
    else:
        report.complete = False
        report.findings.append(ImportFinding(
            code="B002", category="missing_dependency", severity="warning", path="proposal",
            message="RuntimeProposal unavailable; correlation/profile provenance is unavailable.",
            value_state="unavailable",
        ))

    decisions: dict[str, dict[str, Any]] = {}
    bound_decision_ids: list[str] = []
    for i, raw in enumerate(cp["decisions"]):
        raw = _obj(raw, f"decisions[{i}]")
        did = raw.get("decision_id")
        if not isinstance(did, str) or not did:
            raise ImportContractError(f"decisions[{i}].decision_id required")
        _unique_or_same(decisions, did, raw, "decision_id")
        binding = raw.get("binding")
        ids = {"run_id": run_id, "decision_id": did, "effect_id": raw.get("effect_id")}
        if isinstance(binding, dict):
            ids.update({
                "manifest_id": binding.get("manifest_id"),
                "action_id": binding.get("action_id"),
                "grant_id": binding.get("grant_id"),
                "grant_revision": binding.get("grant_revision"),
                "authority_context_instance_id": binding.get("authority_context_id"),
                "requirement_id": binding.get("requirement_id"),
            })
        rec = _record(bounded_profile, "runtime_decision", seq, f"decisions[{i}]", raw,
                      ids=ids, at=raw.get("decided_at"))
        records.append(rec)
        seq += 1
        if isinstance(binding, dict):
            bound_decision_ids.append(did)
            if proposal is not None:
                _validate_proposal_binding(p, binding, f"decisions[{i}].binding")
            effect_id = raw.get("effect_id")
            expected = _sha256({
                "proposal": binding.get("proposal_commitment"),
                "grant_id": binding.get("grant_id"),
                "grant_revision": binding.get("grant_revision"),
            })
            if isinstance(effect_id, str) and effect_id != expected:
                raise ImportContractError(f"decision {did} has invalid effect identity")
            if isinstance(effect_id, str):
                commitments.append(CommitmentRecord(
                    label="effect_id", value=effect_id, algorithm="SHA-256",
                    canonicalization_profile=CANONICAL_JSON_PROFILE,
                    source_record_id=rec.record_id, source_path=f"decisions[{i}].effect_id",
                    verification_status="checked_match",
                    notes="Checked under pinned Control Plane effect-id contract.",
                ))
            for label in ("proposal_commitment", "manifest_digest", "payload_commitment",
                          "requirement_commitment", "role_mapping_digest"):
                value = binding.get(label)
                if isinstance(value, str) and value:
                    commitments.append(CommitmentRecord(
                        label=label, value=value,
                        algorithm="SHA-256" if value.startswith("sha256:") else "producer-declared",
                        canonicalization_profile=CANONICAL_JSON_PROFILE,
                        source_record_id=rec.record_id,
                        source_path=f"decisions[{i}].binding.{label}",
                        verification_status="attributed_claim",
                    ))

    if proposal is not None and len(bound_decision_ids) > 1:
        raise ImportContractError(
            "single-proposal importer does not support multiple authorization bindings"
        )
    if proposal is not None and not bound_decision_ids:
        report.complete = False
        report.findings.append(ImportFinding(
            code="B005", category="missing_dependency", severity="warning",
            path="decisions", message="Supplied proposal did not resolve to an authorization binding.",
            value_state="unavailable",
        ))

    decision_effects = {did: raw.get("effect_id") for did, raw in decisions.items()}
    known_effects = {value for value in decision_effects.values() if isinstance(value, str)}

    attempt_invariants: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(cp["attempts"]):
        raw = _obj(raw, f"attempts[{i}]")
        aid = raw.get("attempt_id")
        if not isinstance(aid, str) or not aid:
            raise ImportContractError(f"attempts[{i}].attempt_id required")
        did = raw.get("decision_id")
        eid = raw.get("effect_id")
        if did not in decision_effects:
            raise ImportContractError(f"attempts[{i}] has dangling decision_id {did}")
        if decision_effects[did] != eid:
            raise ImportContractError(f"attempts[{i}] effect_id does not match its decision")
        invariant = {k: raw.get(k) for k in ("attempt_id", "effect_id", "decision_id", "started_at")}
        prior = attempt_invariants.get(aid)
        started_changed = (prior is not None and prior != invariant
                           and all(prior[k] == invariant[k] for k in prior if k != "started_at"))
        _unique_or_same(attempt_invariants, aid, invariant, "attempt_id",
                        "attempt_started_at_changed" if started_changed else None)
        records.append(_record(
            bounded_profile, "control_plane_attempt_transition", seq, f"attempts[{i}]", raw,
            ids={"run_id": run_id, "attempt_id": aid, "effect_id": raw.get("effect_id"),
                 "decision_id": raw.get("decision_id")},
            at=raw.get("started_at"),
        ))
        seq += 1

    for kind, field, time_field in (
        ("effect_observation", "observations", "observed_at"),
        ("reconciliation", "reconciliations", "reconciled_at"),
    ):
        for i, raw in enumerate(cp[field]):
            raw = _obj(raw, f"{field}[{i}]")
            eid = raw.get("effect_id")
            if eid not in known_effects:
                raise ImportContractError(f"{field}[{i}] has dangling effect_id {eid}")
            if field == "reconciliations" and not repaired:
                embedded = _obj(raw.get("observation"), f"{field}[{i}].observation")
                if embedded.get("effect_id") != eid:
                    raise ImportContractError(f"{field}[{i}].observation.effect_id conflicts with enclosing effect_id")
                if raw.get("result") == "applied" and embedded.get("state") != "applied":
                    raise ImportContractError(f"{field}[{i}] applied result conflicts with embedded observation")
                if raw.get("result") == "safe_to_retry" and embedded.get("state") != "absent":
                    raise ImportContractError(f"{field}[{i}] safe_to_retry conflicts with embedded observation")
            records.append(_record(
                bounded_profile, kind, seq, f"{field}[{i}]", raw,
                ids={"run_id": run_id, "effect_id": raw.get("effect_id")},
                at=raw.get(time_field),
            ))
            seq += 1

    if extended:
        for field, kind in EXTENDED.items():
            rows = [cp[field]] if field == "input_time_floors" else cp[field]
            for i, raw in enumerate(rows):
                records.append(_record(bounded_profile, kind, seq,
                    field if field == "input_time_floors" else f"{field}[{i}]", raw,
                    ids={"run_id":run_id, **({k:raw.get(k) for k in ("decision_id","effect_id","attempt_id","refusal_id","check_id")} if field != "input_time_floors" else {})},
                    at=raw.get("recorded_at",raw.get("evaluated_at",raw.get("reconciled_at"))) if field != "input_time_floors" else None))
                seq += 1

    if programme2:
        _P2_IDS = {"operations": ("operation_id",), "operation_renewals": ("renewal_id", "operation_id"),
                   "attempt_joins": ("join_id", "operation_id", "attempt_id", "effect_id", "decision_id", "check_id"),
                   "rule_revisions": ("revision_id", "rule_ref"), "rule_revision_refusals": ("refusal_id",),
                   "age_extensions": ("extension_id",), "age_extension_refusals": ("refusal_id",), "recovery_runs": ("run_id",),
                   "merge_records": ("merge_id", "survivor_operation_id"), "compensation_obligations": ("obligation_id", "merge_id"),
                   "snapshot_uses": ("use_id", "check_id"), "dedupe_escalations": ("escalation_id", "effect_id", "operation_id")}
        for field, kind in _P2_LISTS.items():
            for i, raw in enumerate(cp.get(field) or []):
                records.append(_record(bounded_profile, kind, seq, f"{field}[{i}]", raw,
                                       ids={"run_id": run_id, **{k: raw.get(k) for k in _P2_IDS[field]}},
                                       at=raw.get("recorded_at", raw.get("admitted_at"))))
                seq += 1

    if proposal is not None:
        profile_ref = proposal.get("authority_context_ref")
        instances = {
            d.get("binding", {}).get("authority_context_id")
            for d in cp["decisions"]
            if isinstance(d, dict) and isinstance(d.get("binding"), dict)
        }
        if profile_ref and profile_ref in instances:
            report.findings.append(ImportFinding(
                code="B003", category="conversion_warning", severity="warning",
                path="proposal.authority_context_ref",
                message="Profile reference equals a context-instance identifier; semantics remain distinct.",
            ))

    profiles = [ProducerProfile(
        profile_id=bounded_profile,
        producer="Cognous Agent Control Plane",
        repository="cogno-us/cognous-agent-control-plane",
        revision=control_plane_revision,
        format_name="BoundedRunRecord",
        format_version=None,
        notes="No embedded format version; adapter is revision-pinned.",
    )]

    if moltbot_export is not None:
        mr, ml, mc, mf = _import_moltbot(
            moltbot_export, seq, records,
            proposal=p if proposal is not None else None,
            profile_id=contract["profile_id"],
        )
        records.extend(mr); links.extend(ml); commitments.extend(mc); report.findings.extend(mf)
        profiles.append(ProducerProfile(
            profile_id=contract["profile_id"],
            producer="Moltbot Safe",
            repository="cogno-us/moltbot-safe",
            revision=contract["repository_revision"],
            format_name="Executor producer export" if not contract["legacy"] else "ExecutionEnvelope + SQLite evidence",
            format_version=contract["interface_profile_version"] or "0.2.0",
            notes=(
                "Versioned producer profile; repository provenance remains source-asserted unless separately established."
                if not contract["legacy"]
                else "Legacy unversioned export accepted only by revision-pinned compatibility handling."
            ),
        ))
    else:
        report.complete = False
        report.findings.append(ImportFinding(
            code="B004", category="missing_dependency", severity="warning",
            path="moltbot_export", message="Executor/destination evidence absent.",
            value_state="absent",
        ))
        if proposal is not None:
            # No executor operation to compare with: the proposal is what the decision's binding commits to, so a journal
            # observation's destination state is compared to it (target, amount, unit, payload, grant, effect).
            grants = {d.get("effect_id"): (d.get("binding") or {}).get("grant_id")
                      for d in cp["decisions"] if isinstance(d, dict) and isinstance(d.get("binding"), dict)}
            committed = {k: p.get(k) for k in ("target", "amount", "unit", "payload")}
            for r in records:
                if r.record_type == "effect_observation" and r.data.get("effect_id") in grants:
                    seen = dict(r.data)  # the operation digest needs the executor's operation, which is absent here
                    if isinstance(seen.get("destination_state"), dict):
                        seen["destination_state"] = {k: v for k, v in seen["destination_state"].items() if k != "operation_digest"}
                    _validate_observation_content(
                        seen, r.data["effect_id"], {**committed, "grant_id": grants[r.data["effect_id"]]},
                        "control_plane.observations")

    if repaired and any(not r.get("observation_accepted") for r in cp["reconciliations"]):
        report.findings.append(ImportFinding(
            code="B020", category="value_state", severity="info",
            path="reconciliations", value_state="unknown",
            message="Historical rejected/unavailable observations are fully retained. This finding does not determine latest delivery state or reconstruction completeness.",
        ))
    unresolved = any(
        r.record_type == "effect_observation" and r.data.get("state") in {"partial", "unknown"}
        for r in records
    )
    if unresolved and not repaired:
        # Preserve the historical revision-selected decoder behavior.
        report.complete = False

    return ReconstructionBundle(
        run_id=run_id,
        status="reconstruction_complete" if report.complete else "reconstruction_partial",
        producer_profiles=profiles,
        records=records,
        links=links,
        commitments=commitments,
        import_reports=[report],
        semantics={
            "record_reconstruction": True,
            "policy_reevaluation": False,
            "model_reexecution": False,
            "external_effect_execution": False,
            "destination_observation": "producer_reported" if moltbot_export else "not_performed",
            "independent_effect_verification": False,
            "notes": "Replay reconstructs recorded events only; import never renews permission or creates an effect.",
        },
        metadata={
            **({"effect_observation_history": _effect_observation_history(cp)} if repaired else {}),
            "control_plane_revision": control_plane_revision,
            "moltbot_safe_revision": contract["repository_revision"] if moltbot_export else None,
            "moltbot_producer_contract": contract if moltbot_export else None,
            "manifest_revision": {CONTROL_PLANE_SECURITY_REVISION: MANIFEST_SECURITY_REVISION,
                                  CONTROL_PLANE_F5B_REVISION: MANIFEST_F5B_REVISION,
                                  CONTROL_PLANE_P4_REVISION: MANIFEST_P4_REVISION,
                                  CONTROL_PLANE_P2_REVISION: MANIFEST_P2_REVISION}.get(control_plane_revision, MANIFEST_REVISION),
            **({"executor_failure_reference_verification": "source_asserted_not_independently_verified"} if control_plane_revision in SECURITY_RUNTIME_CP_REVISIONS else {}),
            "alvorada_revision": ALVORADA_REVISION,
        },
    )


def _import_moltbot(
    source: dict[str, Any], seq: int, cp_records: list[SourceRecord],
    *, proposal: dict[str, Any] | None, profile_id: str,
):
    source = _obj(source, "moltbot_export")
    required = {"execution_envelope", "execution_result", "effects", "attempts", "attempt_events"}
    missing = sorted(required - set(source))
    if missing:
        raise ImportContractError("Moltbot export missing: " + ",".join(missing))
    _reject_unknown_members(source, MOLTBOT_EXPORT_MEMBERS, "moltbot_export")
    if isinstance(source.get("producer_profile"), dict):
        _reject_unknown_members(source["producer_profile"], MOLTBOT_PRODUCER_PROFILE_MEMBERS,
                                "moltbot_export.producer_profile")
    if isinstance(source.get("repository"), dict):
        _reject_unknown_members(source["repository"], MOLTBOT_REPOSITORY_MEMBERS,
                                "moltbot_export.repository")

    envelope = _obj(source["execution_envelope"], "execution_envelope")
    if envelope.get("version") != "0.2.0":
        raise ImportContractError("unsupported Moltbot ExecutionEnvelope version")
    op = _obj(envelope.get("operation"), "execution_envelope.operation")

    cp_decision_records = {
        r.identifiers.get("decision_id"): r
        for r in cp_records if r.record_type == "runtime_decision"
    }
    cp_decisions = {
        did: record.identifiers.get("effect_id")
        for did, record in cp_decision_records.items()
    }
    envelope_decision = envelope.get("decision_id")
    envelope_effect = envelope.get("effect_id")
    if envelope_decision not in cp_decisions:
        raise ImportContractError(f"Moltbot envelope has dangling decision_id {envelope_decision}")
    if cp_decisions[envelope_decision] != envelope_effect:
        raise ImportContractError("Moltbot envelope effect_id does not match Control Plane decision")
    decision_record = cp_decision_records[envelope_decision]
    binding = decision_record.data.get("binding")
    if not isinstance(binding, dict):
        raise ImportContractError("Moltbot envelope cannot bind to a Control Plane decision without authorization binding")
    if proposal is None:
        raise ImportContractError("Moltbot envelope requires the corresponding RuntimeProposal for cross-record validation")
    _validate_proposal_binding(proposal, binding, "decision.binding")
    _validate_envelope_chain(op, proposal, binding)
    expected_operation_digest = _sha256(op)

    versioned_contract = source.get("producer_profile") is not None
    if versioned_contract:
        # control_plane_attempts and observations are optional members of the lifecycle contract (RP-11).
        for field in ("attempt_identity",):
            if field not in source:
                raise ImportContractError(
                    f"versioned Moltbot export missing: {field}"
                )

    records: list[SourceRecord] = []
    links: list[RecordLink] = []
    commitments: list[CommitmentRecord] = []
    findings: list[ImportFinding] = []

    er = _record(
        profile_id, "execution_envelope", seq, "moltbot.execution_envelope", envelope,
        ids={
            "decision_id": envelope.get("decision_id"), "effect_id": envelope.get("effect_id"),
            "requested_attempt_id": envelope.get("attempt_id"),
            "manifest_id": op.get("manifest_id"), "action_id": op.get("action_id"),
            "grant_id": op.get("grant_id"), "grant_revision": op.get("grant_revision"),
            "authority_context_profile_ref": op.get("authority_context_id"),
            "institution_id": op.get("institution_id"), "authority_domain": op.get("authority_domain"),
        },
    )
    records.append(er); seq += 1
    pc = op.get("payload_commitment")
    if isinstance(pc, str):
        if _sha256(op.get("payload", {})) != pc:
            raise ImportContractError("Moltbot envelope payload commitment mismatch")
        commitments.append(CommitmentRecord(
            label="payload_commitment", value=pc, algorithm="SHA-256",
            canonicalization_profile=CANONICAL_JSON_PROFILE,
            source_record_id=er.record_id,
            source_path="moltbot.execution_envelope.operation.payload_commitment",
            verification_status="checked_match",
        ))

    result = _obj(source["execution_result"], "execution_result")
    # decision_id / effect_id are optional result members of the lifecycle contract: absent is accepted, present
    # must match the envelope.
    if (result.get("decision_id", envelope_decision) != envelope_decision
            or result.get("effect_id", envelope_effect) != envelope_effect):
        raise ImportContractError("Moltbot execution_result identifiers do not match execution envelope",
                                  "result_binding_mismatch")
    if source.get("producer_profile", {}).get("profile_version") == "2.0.0":
        _validate_v2_export(source, cp_records, op, envelope_effect)
        for kind, path, value in (
            ("executor_control_plane_evidence", "control_plane_evidence", source["control_plane_evidence"]),
            *(("rejected_executor_observation", f"rejected_observations[{i}]", item)
              for i, item in enumerate(source["rejected_observations"])),
        ):
            records.append(_record(profile_id, kind, seq, "moltbot." + path, value))
            seq += 1
        if result.get("status") == "observed":
            findings.append(ImportFinding(code="M020", category="unsupported_semantic",
                severity="info", path="execution_result.observation",
                message="Historical local observation is retained without Control Plane validation or renewed authority."))

    result_observation = result.get("observation")
    if _is_recovery_observation(result_observation):
        findings.append(ImportFinding(code="M021", category="unsupported_semantic",
            severity="info", path="execution_result.observation",
            message="Destination recovery report is retained as a report only; it is not a validated Control Plane observation."))
    elif isinstance(result_observation, dict) and result_observation:
        _require_equal(result_observation.get("effect_id"), envelope_effect, "execution_result.observation.effect_id",
                       "result_binding_mismatch")
        if "state" in result_observation and result.get("observed_state") not in (None, "unknown"):
            _require_equal(result_observation.get("state"), result.get("observed_state"), "execution_result.observation.state")
        if "destination_state" in result_observation:
            _validate_observation_content(
                result_observation, envelope_effect, op, "execution_result.observation"
            )
    records.append(_record(
        profile_id, "execution_result", seq, "moltbot.execution_result", result,
        ids={"decision_id": result.get("decision_id"), "effect_id": result.get("effect_id"),
             "attempt_id": result.get("attempt_id")},
    )); seq += 1

    attempts: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(source["attempts"]):
        raw = _obj(raw, f"moltbot.attempts[{i}]")
        aid = raw.get("attempt_id")
        if not isinstance(aid, str) or not aid:
            raise ImportContractError("Moltbot attempt missing attempt_id")
        if raw.get("decision_id") != envelope_decision or raw.get("effect_id") != envelope_effect:
            raise ImportContractError(f"Moltbot attempt {aid} does not match execution envelope")
        digest = raw.get("operation_digest", expected_operation_digest)  # optional member of the contract
        if digest not in (expected_operation_digest, "legacy:unknown"):
            raise ImportContractError(f"Moltbot attempt {aid} operation_digest mismatch")
        _unique_or_same(attempts, aid, raw, "Moltbot attempt_id")
        records.append(_record(
            profile_id, "destination_attempt", seq, f"moltbot.attempts[{i}]", raw,
            ids={"attempt_id": aid, "effect_id": raw.get("effect_id"), "decision_id": raw.get("decision_id")},
        )); seq += 1

    for i, raw in enumerate(source["attempt_events"]):
        raw = _obj(raw, f"moltbot.attempt_events[{i}]")
        aid = raw.get("attempt_id")
        if aid not in attempts:
            raise ImportContractError(f"dangling Moltbot attempt event: {aid}")
        records.append(_record(
            profile_id, "destination_attempt_event", seq, f"moltbot.attempt_events[{i}]", raw,
            ids={"attempt_id": aid, "event_id": raw.get("event_id"),
                 "effect_id": attempts[aid].get("effect_id"), "decision_id": attempts[aid].get("decision_id")},
        )); seq += 1

    if source.get("producer_profile", {}).get("profile_version") == "2.0.0":
        _validate_v2_executor_rows(source, attempts, result)

    cp_attempt_records = {
        r.identifiers.get("attempt_id"): r
        for r in cp_records
        if r.record_type == "control_plane_attempt_transition"
        and isinstance(r.identifiers.get("attempt_id"), str)
    }
    supplied_cp_attempts = source.get("control_plane_attempts") or []
    if not isinstance(supplied_cp_attempts, list):
        raise ImportContractError("control_plane_attempts must be an array")
    supplied_cp_by_id: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(supplied_cp_attempts):
        raw = _obj(raw, f"moltbot.control_plane_attempts[{i}]")
        aid = raw.get("attempt_id")
        if not isinstance(aid, str) or not aid:
            raise ImportContractError(
                f"moltbot.control_plane_attempts[{i}].attempt_id required"
            )
        owner_record = cp_attempt_records.get(aid)
        if owner_record is None:
            raise ImportContractError(
                f"Control Plane attempt evidence has no owning producer record: {aid}"
            )
        if owner_record.data != raw:
            raise ImportContractError(
                f"Control Plane attempt evidence conflicts with owning producer record: {aid}"
            )
        if raw.get("decision_id") != envelope_decision:
            raise ImportContractError(
                f"Control Plane attempt evidence {aid} decision binding mismatch"
            )
        if raw.get("effect_id") != envelope_effect:
            raise ImportContractError(
                f"Control Plane attempt evidence {aid} effect binding mismatch"
            )
        _unique_or_same(
            supplied_cp_by_id, aid, raw, "supplied Control Plane attempt_id"
        )
        records.append(_record(
            owner_record.producer_profile_id,
            "moltbot_attributed_control_plane_attempt",
            seq,
            f"moltbot.control_plane_attempts[{i}]",
            raw,
            ids={
                "run_id": cp_records[0].identifiers.get("run_id") if cp_records else None,
                "attempt_id": aid,
                "decision_id": raw.get("decision_id"),
                "effect_id": raw.get("effect_id"),
            },
        ))
        seq += 1
        links.append(RecordLink(
            link_type="explicit",
            from_record_id=records[-1].record_id,
            to_record_id=owner_record.record_id,
            basis="Producer-supplied Control Plane attempt evidence exactly matches the retained Control Plane run record.",
            establishes_identity_equivalence=True,
        ))

    attempt_identity = source.get("attempt_identity")
    if attempt_identity is not None:
        attempt_identity = _obj(attempt_identity, "moltbot.attempt_identity")
        namespace = attempt_identity.get("namespace")
        owner = attempt_identity.get("owner")
        aid = attempt_identity.get("attempt_id")
        if not isinstance(aid, str) or not aid:
            raise ImportContractError("attempt_identity.attempt_id required")
        if namespace == "executor":
            if owner != "cogno-us/moltbot-safe":
                raise ImportContractError("executor attempt_identity owner mismatch")
            if aid not in attempts:
                raise ImportContractError(
                    f"executor attempt_identity has dangling attempt_id {aid}"
                )
        elif namespace == "control_plane":
            if owner != "cogno-us/cognous-agent-control-plane":
                raise ImportContractError("Control Plane attempt_identity owner mismatch")
            if aid not in supplied_cp_by_id:
                raise ImportContractError(
                    f"Control Plane attempt_identity lacks attributed producer evidence: {aid}"
                )
        else:
            raise ImportContractError("unsupported attempt_identity namespace")

    result_attempt_id = result.get("attempt_id")
    if result_attempt_id is not None:
        if not isinstance(result_attempt_id, str) or not result_attempt_id:
            raise ImportContractError("execution_result.attempt_id must be a non-empty string when supplied")
        if versioned_contract:
            if attempt_identity is None:
                raise ImportContractError(
                    "versioned execution_result attempt_id requires attempt_identity"
                )
            if attempt_identity.get("attempt_id") != result_attempt_id:
                raise ImportContractError(
                    "execution_result attempt_id conflicts with attempt_identity"
                )
            if attempt_identity.get("namespace") == "control_plane":
                if result.get("status") not in {"reconciled", "partial", "unknown"}:
                    raise ImportContractError(
                        "Control Plane attempt namespace is valid only for reconciliation/partial/unknown results"
                    )
                if result.get("newly_executed") is not False:
                    raise ImportContractError(
                        "Control Plane attempt namespace cannot represent a newly executed effect"
                    )
            elif attempt_identity.get("namespace") == "executor":
                if result_attempt_id not in attempts:
                    raise ImportContractError(
                        f"execution_result has dangling executor attempt_id {result_attempt_id}"
                    )
        else:
            moltbot_ids = set(attempts)
            cp_attempt_ids = set(cp_attempt_records)
            if result_attempt_id not in moltbot_ids and result_attempt_id not in cp_attempt_ids:
                raise ImportContractError(f"execution_result has dangling attempt_id {result_attempt_id}")
            if result_attempt_id in cp_attempt_ids and result_attempt_id not in moltbot_ids:
                if result.get("status") not in {"reconciled", "partial", "unknown"} or result.get("newly_executed") is not False:
                    raise ImportContractError(
                        "Control Plane attempt namespace is valid only for non-new reconciliation results"
                    )
    elif versioned_contract and attempt_identity is not None:
        raise ImportContractError(
            "attempt_identity supplied when execution_result.attempt_id is absent"
        )

    effects: dict[str, dict[str, Any]] = {}
    for i, raw in enumerate(source["effects"]):
        raw = _obj(raw, f"moltbot.effects[{i}]")
        eid = raw.get("effect_id")
        if not isinstance(eid, str) or not eid:
            raise ImportContractError("Moltbot effect missing effect_id")
        invariant = {k: raw.get(k) for k in
                     ("effect_id", "operation_digest", "grant_id", "target", "amount", "unit", "payload_json")}
        if eid != envelope_effect:
            raise ImportContractError("Moltbot effect_id does not match execution envelope")
        if raw.get("operation_digest") != expected_operation_digest:
            raise ImportContractError("Moltbot effect operation_digest mismatch")
        _require_equal(raw.get("grant_id"), op.get("grant_id"), f"moltbot.effects[{i}].grant_id")
        _require_equal(raw.get("target"), op.get("target"), f"moltbot.effects[{i}].target")
        _require_equal(raw.get("amount"), op.get("amount"), f"moltbot.effects[{i}].amount")
        _require_equal(raw.get("unit"), op.get("unit"), f"moltbot.effects[{i}].unit")
        _require_equal(
            _decode_payload_json(raw.get("payload_json"), f"moltbot.effects[{i}].payload_json"),
            op.get("payload"), f"moltbot.effects[{i}].payload_json",
        )
        if eid in effects and source.get("producer_profile", {}).get("profile_version") == "2.0.0":
            raise ImportContractError(f"duplicate destination effect row for {eid}")
        _unique_or_same(effects, eid, invariant, "effect_id")
        rr = _record(
            profile_id, "destination_effect", seq, f"moltbot.effects[{i}]", raw,
            ids={"effect_id": eid, "grant_id": raw.get("grant_id")},
        )
        records.append(rr); seq += 1
        digest = raw.get("operation_digest")
        if isinstance(digest, str):
            commitments.append(CommitmentRecord(
                label="operation_digest", value=digest, algorithm="SHA-256",
                canonicalization_profile=CANONICAL_JSON_PROFILE,
                source_record_id=rr.record_id, source_path=f"moltbot.effects[{i}].operation_digest",
                verification_status="checked_match",
                notes="Checked against the exact retained Execution Envelope operation under the pinned canonicalization profile.",
            ))

    status = result.get("status")
    observed_state = result.get("observed_state")
    if status in {"executed", "reconciled", "partial"} and observed_state in {"applied", "partial"} and not effects:
        raise ImportContractError(
            "execution result requires retained destination effect evidence"
        )
    if status == "observed" and observed_state in {"applied", "partial"} and not effects:
        raise ImportContractError(
            "historical observation requires retained destination effect evidence"
        )
    if status in {"denied"} and effects:
        raise ImportContractError("denied execution result contradicts retained effect evidence")
    if status == "observed" and observed_state in {"absent", "unknown"} and effects:
        raise ImportContractError(
            "absence/unknown observation contradicts retained destination effect evidence"
        )

    recovery_retained = False

    def retain_recovery_report(raw: dict[str, Any], path: str) -> None:
        # Destination recovery report (route B): retained under its own record type so that it can never be
        # read as a validated executor observation. Its content was checked by the producer-2.0.0 export gate.
        nonlocal seq, recovery_retained
        records.append(_record(
            profile_id, "executor_recovery_report", seq, path, raw,
            ids={"effect_id": raw.get("effect_id") or envelope_effect},
        ))
        seq += 1
        recovery_retained = True

    for i, raw in enumerate(source.get("observations") or []):
        raw = _obj(raw, f"moltbot.observations[{i}]")
        if _is_recovery_observation(raw):
            # Legacy layout: the recovery report is mirrored in ``observations``. Tolerated until the contract
            # freezes; the new layout carries it in ``recovery_observations``.
            retain_recovery_report(raw, f"moltbot.observations[{i}]")
            continue
        _validate_observation_content(raw, envelope_effect, op, f"moltbot.observations[{i}]")
        if raw.get("state") in {"absent", "unknown"}:
            destination_state = raw.get("destination_state")
            if isinstance(destination_state, dict) and destination_state:
                raise ImportContractError(
                    f"moltbot.observations[{i}] absence/unknown must not fabricate destination_state"
                )
        records.append(_record(
            profile_id, "executor_observation", seq, f"moltbot.observations[{i}]", raw,
            ids={"effect_id": raw.get("effect_id")},
        ))
        seq += 1
    for i, raw in enumerate(source.get("recovery_observations") or []):
        retain_recovery_report(_obj(raw, f"moltbot.recovery_observations[{i}]"), f"moltbot.recovery_observations[{i}]")
    if not recovery_retained and _is_recovery_observation(result_observation):
        # New layout without the optional ``recovery_observations`` member: the report is carried by the result only.
        retain_recovery_report(result_observation, "moltbot.execution_result.observation")
    if isinstance(source.get("extensions"), dict):
        _check_extensions(source, "moltbot_export")
        # Export-level extensions are retained verbatim as their own record (digested with it), never interpreted.
        records.append(_record(profile_id, "executor_export_extensions", seq, "moltbot.extensions",
                               source["extensions"]))
        seq += 1

    cp_attempts = [
        r for r in cp_records
        if r.record_type == "control_plane_attempt_transition"
    ]
    for cr in cp_attempts:
        ack = cr.data.get("acknowledgement")
        if isinstance(ack, dict) and isinstance(ack.get("attempt_id"), str):
            local_id = ack["attempt_id"]
            matches = [
                r for r in records
                if r.record_type == "destination_attempt"
                and r.identifiers.get("attempt_id") == local_id
            ]
            if len(matches) == 1:
                links.append(RecordLink(
                    link_type="explicit",
                    from_record_id=cr.record_id,
                    to_record_id=matches[0].record_id,
                    basis="Control Plane acknowledgement explicitly supplied executor attempt_id.",
                    establishes_identity_equivalence=False,
                ))
            else:
                if profile_id in STRICT_ACK_PROFILES:
                    raise ImportContractError("explicit executor attempt reference is dangling or ambiguous")
                findings.append(ImportFinding(
                    code="M001",
                    category="missing_dependency",
                    severity="warning",
                    path=cr.source_path + ".acknowledgement.attempt_id",
                    message="Explicit executor attempt ID did not resolve uniquely.",
                    value_state="unavailable",
                ))

    if cp_attempts and attempts and not any(
        link.to_record_id.startswith(profile_id + ":destination_attempt")
        for link in links
    ):
        findings.append(ImportFinding(
            code="M002",
            category="unsupported_semantic",
            severity="warning",
            path="attempt_correlation",
            message="Control Plane and executor attempt namespaces are preserved separately; no equivalence is inferred.",
            value_state="unknown",
        ))
    findings.append(ImportFinding(
        code="M003", category="conversion_warning", severity="info",
        path="moltbot.execution_envelope.operation.institution_id",
        message="Institution/domain provenance is the trusted Moltbot integration context, not Control Plane AuthorizationBinding.",
    ))
    findings.append(ImportFinding(
        code="M004", category="conversion_warning", severity="info",
        path="moltbot.execution_envelope.operation.authority_context_id",
        message="At the pinned adapter this field carries the proposal profile reference; it is distinct from the Control Plane binding context-instance ID.",
    ))
    return records, links, commitments, findings


def _accepted_repaired_observation(observation: dict[str, Any], effect: str) -> None:
    _require_equal(observation.get('effect_id'), effect, 'accepted observation.effect_id')
    state = observation.get('state')
    destination = observation.get('destination_state')
    if state in {'applied', 'partial'}:
        destination = _obj(destination, 'accepted observation.destination_state')
        _require_equal(destination.get('effect_id'), effect, 'accepted destination.effect_id')
        _require_equal(destination.get('state'), state, 'accepted destination.state')
    elif state == 'absent':
        if destination != {}:
            raise ImportContractError('accepted absence contains destination content')
    else:
        raise ImportContractError('unsupported accepted observation state')


def _aware_time(value: Any) -> datetime:
    result = parse_instant(value)
    if result is None:
        raise ImportContractError('accepted observation requires timezone-aware times')
    return result


def _validate_programme2_members(cp: dict[str, Any]) -> None:
    """Programme-2 opt-in profile members (see programme2_profiles): structure, then cross-row couplings."""
    from . import programme2_profiles as p2
    try:
        p2.validate_rows(cp)
        p2.validate_cross_rows(cp)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ImportContractError("programme-2 profile: malformed profile member: " + repr(exc), "schema_violation") from exc


# Attempt state machines of the lifecycle contract (decision 37; 39-P adds executed/partial -> unknown, the Control Plane
# adapter appends 'unknown' when the follow-up observation is not accepted). A status without successor is closed: a
# closed attempt is never reopened and never receives a later, contradicting record (``attempt_transition``).
EXECUTOR_ATTEMPT_TRANSITIONS: dict[str, frozenset[str]] = {
    "attempted": frozenset({"executed", "partial", "failed", "unknown", "denied", "reconciled"}),
    "unknown": frozenset({"executed", "partial", "failed", "reconciled"}),
    "executed": frozenset({"unknown", "reconciled"}),
    "partial": frozenset({"unknown", "reconciled"}),
    "failed": frozenset(),
    "denied": frozenset(),
    "reconciled": frozenset(),
}
CONTROL_PLANE_ATTEMPT_TRANSITIONS: dict[str, frozenset[str]] = {
    "attempted": frozenset({"acknowledged", "unknown", "failed", "partial"}),
    "unknown": frozenset({"acknowledged", "failed", "partial"}),
    "acknowledged": frozenset(),
    "partial": frozenset(),
    "failed": frozenset(),
}


def _validate_repaired_run(cp: dict[str, Any], *, profiles: bool = False) -> None:
    """Check recorded contract consistency; no authority evaluation or new observation."""
    accepted = []
    for raw in cp.get('reconciliations', []):
        rec = _obj(raw, 'reconciliation')
        if rec.get('retry_eligible') is not False:
            raise ImportContractError('repaired reconciliation cannot establish retry eligibility')
        if type(rec.get('observation_accepted')) is not bool:
            raise ImportContractError('reconciliation observation_accepted must be explicit')
        reasons = rec.get('reasons')
        if not isinstance(reasons, list) or not all(isinstance(x, str) and x for x in reasons):
            raise ImportContractError('reconciliation reasons must be an array of reasons')
        observation = rec.get('observation')
        if not rec['observation_accepted']:
            if rec.get('result') != 'hold' or not reasons:
                raise ImportContractError('rejected/unavailable observation must hold with reasons')
            if observation is not None:
                _obj(observation, 'rejected observation')
            # Wrong-effect and malformed-time evidence remains attributed rejected
            # content, never an identifier or accepted observation record.
            continue
        observation = _obj(observation, 'accepted reconciliation.observation')
        _accepted_repaired_observation(observation, rec.get('effect_id'))
        if reasons:
            raise ImportContractError('accepted observation has rejection reasons')
        maximum = rec.get('observation_max_age_seconds')
        tolerance = rec.get('observation_clock_tolerance_seconds')
        if type(maximum) is not int or maximum <= 0 or type(tolerance) is not int or tolerance < 0:
            raise ImportContractError('accepted reconciliation requires explicit observation policy')
        evaluation = _aware_time(rec.get('evaluation_time'))
        observed = _aware_time(observation.get('observed_at'))
        age = (evaluation - observed).total_seconds()
        # freshness/0.1 judges "future" against the service clock re-read at reconciliation, not the evaluation pass (an
        # observation the checked party stamped after the pass began is not future); staleness stays relative to the
        # evaluation. The row's reconciled_at is that clock, so it is the reference when the run carries the clocks.
        reference = evaluation
        if profiles and freshness_on(cp):
            reference = max(evaluation, _aware_time(rec.get('reconciled_at')))
        if age > maximum or (reference - observed).total_seconds() < -tolerance:
            raise ImportContractError('accepted observation violates recorded temporal policy')
        expected = {'applied': 'applied', 'absent': 'observed_absent', 'partial': 'hold'}[observation['state']]
        if rec.get('result') != expected:
            raise ImportContractError('reconciliation result contradicts accepted observation')
        accepted.append(observation)
    if cp.get('observations') != accepted:
        raise ImportContractError('accepted Control Plane observations differ from retained reconciliations')
    terminal = {}
    lifecycle: dict[Any, list[dict[str, Any]]] = {}
    for i, attempt in enumerate(cp.get('attempts', [])):
        attempt = _obj(attempt, 'attempt')
        _validate_control_plane_attempt_row(attempt, f'attempts[{i}]', extra=_P2_ATTEMPT_MEMBERS if profiles else frozenset())
        previous = lifecycle.get(attempt.get('attempt_id'))
        if previous and any((row.get('effect_id'), row.get('decision_id')) != (attempt.get('effect_id'), attempt.get('decision_id'))
                            for row in previous[:1]):
            # effect_id and decision_id are fixed by the first row of an attempt and identical on every later row.
            raise ImportContractError(
                f"Control Plane attempt {attempt.get('attempt_id')} changed its effect_id or decision_id between lifecycle rows",
                'attempt_identity_changed')
        if attempt.get('status') != 'attempted':
            reopened = (previous is not None and previous[0].get('status') == 'attempted' and previous[-1] != attempt
                        and attempt.get('status') not in CONTROL_PLANE_ATTEMPT_TRANSITIONS.get(previous[-1].get('status'), frozenset()))
            _unique_or_same(terminal, attempt.get('attempt_id'), attempt, 'terminal Control Plane attempt',
                            'attempt_transition' if reopened else None)
        lifecycle.setdefault(attempt.get('attempt_id'), []).append(attempt)
    # Each attempt lifecycle starts with exactly one 'attempted' record; no lifecycle record is repeated
    # verbatim. A dropped start record or a duplicated record is a defect, not repeated history.
    for attempt_id, rows in lifecycle.items():
        # Control Plane bounded.py mints a single-record attempt (no 'attempted' start) when it reconciles an
        # already-applied/partial effect; that record is marked acknowledgement={'reconciled_existing': True}.
        # The marker is valid only as the whole acknowledgement of a lone acknowledged/partial record, and when
        # present it must be exactly true.
        reconciled_only = (len(rows) == 1 and rows[0].get('status') in {'acknowledged', 'partial'}
                           and rows[0].get('acknowledgement') == {'reconciled_existing': True}
                           and rows[0]['acknowledgement']['reconciled_existing'] is True)
        marked = any('reconciled_existing' in row['acknowledgement'] for row in rows)
        if marked and not reconciled_only:
            raise ImportContractError(f'Control Plane attempt {attempt_id} carries an invalid reconciled_existing marker',
                                      'invalid_reconciled_marker')
        if rows[0].get('status') != 'attempted' and not reconciled_only:
            raise ImportContractError(f'Control Plane attempt {attempt_id} lifecycle lacks its attempted start record',
                                      'missing_start_record')
        if len({row.get('started_at') for row in rows}) > 1:
            raise ImportContractError(f'Control Plane attempt {attempt_id} started_at changed between lifecycle rows',
                                      'attempt_started_at_changed')
        if _has_equal_rows(rows):
            raise ImportContractError(f'Control Plane attempt {attempt_id} lifecycle repeats a record', 'repeated_record')
        if rows[0].get('status') == 'attempted':
            for before, after in zip(rows, rows[1:]):
                if before != after and after.get('status') not in CONTROL_PLANE_ATTEMPT_TRANSITIONS.get(before.get('status'), frozenset()):
                    raise ImportContractError(
                        f"Control Plane attempt {attempt_id} row status {after.get('status')!r} may not follow {before.get('status')!r}",
                        'attempt_transition')


def _freeze(value: Any) -> Any:
    """A hashable form with the same equality as ``==`` on JSON values (dict order ignored; 1, 1.0 and True agree)."""
    if isinstance(value, dict):
        return frozenset((key, _freeze(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def _has_equal_rows(rows: list[Any]) -> bool:
    """True when two rows are equal; one hash-set pass instead of comparing every pair."""
    try:
        seen: set[Any] = set()
        for row in rows:
            key = _freeze(row)
            if key in seen:
                return True
            seen.add(key)
        return False
    except TypeError:  # an unhashable non-JSON scalar: fall back to the pairwise comparison
        return any(rows[i] == rows[j] for i in range(len(rows)) for j in range(i))


def _validate_executor_attempt_rows(source: dict[str, Any],
                                    attempts: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Attempt rows are unique; the attempt events of every executor attempt are present, carry strictly
    increasing event ids and non-decreasing times, start with ``attempted``, are not repeated and move only along
    the attempt state machine. Returns the events of each attempt in order."""
    rows = source["attempts"]
    if len(rows) != len(attempts):
        raise ImportContractError("duplicate executor attempt row", "duplicate_attempt_row")
    events = source["attempt_events"]
    last_id = None
    last_time = None
    per_attempt: dict[str, list[dict[str, Any]]] = {}
    for i, raw in enumerate(events):
        event_id = raw.get("event_id")
        if type(event_id) is not int or (last_id is not None and event_id <= last_id):
            raise ImportContractError(f"moltbot.attempt_events[{i}] event_id is repeated or out of order", "event_order")
        last_id = event_id
        created = raw.get("created_at")
        if isinstance(created, bool) or not isinstance(created, (int, float)) or (last_time is not None and created < last_time):
            raise ImportContractError(f"moltbot.attempt_events[{i}] created_at is missing or out of order", "event_order")
        last_time = created
        per_attempt.setdefault(raw.get("attempt_id"), []).append(raw)
    for aid in attempts:
        rows_for = per_attempt.get(aid)
        if not rows_for:
            raise ImportContractError(f"executor attempt {aid} has no attempt events", "attempt_without_events")
        if rows_for[0].get("status") != "attempted":
            raise ImportContractError(f"executor attempt {aid} events do not start with attempted", "missing_start_event")
        if any(r.get("status") == "attempted" for r in rows_for[1:]):
            raise ImportContractError(f"executor attempt {aid} repeats its attempted event", "repeated_start_event")
        for before, after in zip(rows_for, rows_for[1:]):
            if after.get("status") not in EXECUTOR_ATTEMPT_TRANSITIONS.get(before.get("status"), frozenset()):
                raise ImportContractError(
                    f"executor attempt {aid} event {after.get('status')!r} may not follow {before.get('status')!r}",
                    "attempt_transition")
    return per_attempt


def _validate_v2_executor_rows(source: dict[str, Any], attempts: dict[str, dict[str, Any]],
                               result: dict[str, Any]) -> None:
    """Producer 2.0.0 executor rows must be a complete, ordered, non-repeated lifecycle (see
    ``_validate_executor_attempt_rows``); the terminal event of the attempt that the execution result names equals
    the result status."""
    _validate_result_terminal_event(source, attempts, _validate_executor_attempt_rows(source, attempts), result)


def _validate_result_terminal_event(source: dict[str, Any], attempts: dict[str, dict[str, Any]],
                                    per_attempt: dict[str, list[dict[str, Any]]], result: dict[str, Any]) -> None:
    attempt_identity = source.get("attempt_identity") or {}
    result_attempt = result.get("attempt_id")
    if (attempt_identity.get("namespace") == "executor" and result_attempt in attempts
            and result.get("status") != "observed"):
        terminal = per_attempt[result_attempt][-1].get("status")
        # The Control Plane adapter reports an acknowledged-but-unobserved delivery as result 'unknown'
        # (no validated observation) while the executor's own terminal event is 'executed' (contract exception).
        unresolved_ack = terminal == "executed" and result.get("status") == "unknown"
        if terminal != result.get("status") and not unresolved_ack:
            raise ImportContractError(
                f"execution result status {result.get('status')!r} contradicts the terminal attempt event {terminal!r}",
                "terminal_event_missing" if terminal == "attempted" else "status_terminal_mismatch")


def _validate_export_layout(source: dict[str, Any], observation: Any, kind: str) -> None:
    """Export layout (ODES item 7, step A).

    ``observations`` lists the validated observation the result carries (or is empty); ``recovery_observations`` is
    optional and equals the recovery report the result carries (or is empty). Both members are optional. The legacy
    layout, which mirrored the recovery report in ``observations``, is refused (step B, schema_violation, in the
    structure check; a recovery report in ``observations`` also fails the equality below)."""
    listed = source.get("recovery_observations")
    recovery_expected = [observation] if kind == "recovery" else []
    if listed is not None and listed != recovery_expected:
        raise ImportContractError("recovery_observations differ from the result report", "recovery_observations_mismatch")
    observations = source.get("observations")
    if observations is None:
        return
    validated_expected = [observation] if kind == "validated" else []
    if observations != validated_expected:
        raise ImportContractError("accepted executor observations differ from result", "observations_mismatch")


def _validate_result_contract(result: dict[str, Any], observation: Any, kind: str) -> None:
    """Cross-record result rules of the lifecycle contract that do not depend on recovery-report content."""
    status = result.get("status")
    if kind == "recovery" and status not in {"unknown", "observed"}:
        raise ImportContractError("a recovery report is only carried by results unknown or observed",
                                  "recovery_observation_status")
    if status == "observed" and kind != "recovery" and _claims_attempt(result):
        # 'observed' is the effect-free observation; a normal execution reports 'executed'.
        raise ImportContractError("an observed result cannot claim an attempt, acknowledgement or new effect "
                                  "(a normal execution reports executed)", "observed_result_claims_attempt")
    if status == "executed" and kind == "none":
        raise ImportContractError("an executed result must carry the observation that established it",
                                  "executed_without_observation")


# RP-6, narrowed (contract rule unknown_with_validated_observation). Result unknown may carry a validated observation
# whose state is absent/unknown (always accepted, observed_state must equal observation.state). A result unknown with a
# validated applied/partial observation is refused: owner decision 2026-10-17, enforced since step B (P4), after the
# runtime change (reconciled/partial instead of unknown) merged and the pinned runtimes advanced. Producers older than
# the lifecycle contract (which export a lost ack as unknown + validated applied) are not accepted any more.
ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATION = True


ROUTE_B_EXECUTION_EVIDENCE_MEMBERS = frozenset({"local_authority_effect_profile", "claim_id", "linearized_at", "authority_receipt"})
ROUTE_B_AUTHORITY_PROFILE = "urn:cognous:profiles:local-authority-effect:0.1.0-proposed"


def _validate_route_b_execution_evidence(evidence: dict[str, Any], result: dict[str, Any], effect: str,
                                         decision_id: str, op: dict[str, Any]) -> None:
    """F-28: control_plane_evidence of a normal route-B execution (all four members, bound to the result).

    The receipt is also bound to the grant and revision of the execution envelope's operation (the same members the
    envelope chain binds to the decision), so a receipt for another grant or revision is refused.
    """
    if set(evidence) & ROUTE_B_EXECUTION_EVIDENCE_MEMBERS != ROUTE_B_EXECUTION_EVIDENCE_MEMBERS:
        raise ImportContractError("route B execution evidence is incomplete (profile, claim, linearized_at and "
                                  "authority_receipt are required together)")
    if evidence["local_authority_effect_profile"] != ROUTE_B_AUTHORITY_PROFILE:
        raise ImportContractError("unsupported local authority effect profile")
    claim = evidence["claim_id"]
    if not isinstance(claim, str) or not claim or len(claim) > 200:
        raise ImportContractError("invalid route B claim id")
    linearized = evidence["linearized_at"]
    if not isinstance(linearized, str) or not linearized:
        raise ImportContractError("invalid route B linearized_at")
    if parse_instant(linearized) is None:
        raise ImportContractError("invalid route B linearized_at")
    if (result.get("status") not in {"executed", "partial"} or not result.get("attempted")
            or not result.get("acknowledged") or not result.get("newly_executed")):
        raise ImportContractError("route B authority receipt is only carried by a newly executed result")
    receipt = _obj(evidence["authority_receipt"], "route B authority receipt")
    for field, expected in (("attempt_id", result.get("attempt_id")), ("effect_id", effect),
                            ("decision_id", decision_id), ("claim_id", claim),
                            ("grant_id", op.get("grant_id")), ("grant_revision", op.get("grant_revision")),
                            ("profile", ROUTE_B_AUTHORITY_PROFILE)):
        if expected is None or receipt.get(field) != expected:
            raise ImportContractError(f"route B authority receipt {field} contradicts the execution result")
    if receipt.get("grant_status") != "active":
        raise ImportContractError("route B authority receipt does not show an active grant")


ATTEMPT_CLAIMING_STATUSES = frozenset({"failed", "partial", "unknown", "executed", "reconciled"})
OBSERVED_STATES = frozenset({"applied", "partial", "absent", "unknown"})


def _validate_result_attempt_binding(source: dict[str, Any], result: dict[str, Any]) -> None:
    """Executor attempt rows, events and transitions, then the result's attempt binding (contract rule
    ``result_attempt_unresolved``), then the terminal-event comparison: a result whose status claims an attempt names
    an attempt that the export carries, whatever its flags and observation say. A null attempt_id and an id that matches no row are both refused. The
    attempt may be an executor attempt row or, for a Control Plane attempt namespace result, a Control Plane attempt
    row of the export (which the attempt_identity checks bind further)."""
    rows = source["attempts"]
    if not all(isinstance(row.get("attempt_id"), str) and row["attempt_id"] for row in rows):
        return  # reported by the attempt checks that read the rows
    by_id = {row["attempt_id"]: row for row in rows}
    per_attempt = _validate_executor_attempt_rows(source, by_id)
    if result.get("status") in ATTEMPT_CLAIMING_STATUSES:
        named = result.get("attempt_id")
        control_plane_ids = {row.get("attempt_id") for row in (source.get("control_plane_attempts") or [])
                             if isinstance(row, dict)}
        if not (isinstance(named, str) and named and (named in by_id or named in control_plane_ids)):
            raise ImportContractError(
                f"execution result status {result.get('status')!r} names no attempt row of the export "
                "(a null attempt_id or an id that matches no row is refused)", "result_attempt_unresolved")
    _validate_result_terminal_event(source, by_id, per_attempt, result)


def _result_matrix_problems(result: dict[str, Any]) -> list[str]:
    """What the producer's status matrix refuses about an execution result (contract rule ``result_state_matrix``)."""
    status = result["status"]
    present = {name: result[name] for name in ("attempted", "acknowledged", "newly_executed") if name in result}
    if any(type(value) is not bool for value in present.values()):
        return ["attempted, acknowledged and newly_executed are carried as booleans"]
    if len(present) != 3:  # absent flags are not claimed, so the flag rows have nothing to read
        present = {}
    attempted, acknowledged, fresh = (present.get(name) for name in ("attempted", "acknowledged", "newly_executed"))
    observed_state, observation = result["observed_state"], result["observation"]
    problems: list[str] = []
    if not isinstance(observed_state, str) or observed_state not in OBSERVED_STATES:
        problems.append("observed_state is one of applied, partial, absent, unknown")
    if status in ATTEMPT_CLAIMING_STATUSES and attempted is False:
        problems.append(f"status {status!r} requires an attempted execution")
    if acknowledged and attempted is False:
        problems.append("an acknowledgement requires an attempted execution")
    if fresh and not (acknowledged is True and status in {"executed", "partial", "unknown"}):
        problems.append("a fresh execution is acknowledged and has status executed, partial or unknown")
    if status in {"denied", "failed"} and (acknowledged or fresh or observed_state != "unknown"):
        problems.append("a denied or failed result carries no acknowledgement, no fresh execution and observed_state unknown")
    if status == "executed" and (acknowledged is False or fresh is False or observed_state != "applied"):
        problems.append("an executed result is acknowledged, fresh and observed as applied")
    if status == "reconciled" and (fresh or observed_state != "applied"):
        problems.append("a reconciled result is observed as applied and is not a fresh execution")
    if status == "partial" and observed_state != "partial":
        problems.append("a partial result is observed as partial")
    if status in {"executed", "reconciled", "partial", "observed"} and not isinstance(observation, dict):
        problems.append(f"status {status!r} requires a retained observation")
    if _observation_kind(observation) == "validated" and observation["state"] != observed_state:
        problems.append("a validated observation's state is the result's observed_state")
    return problems


def _validate_v2_export(source: dict[str, Any], cp_records: list[SourceRecord],
                        op: dict[str, Any], effect: str) -> None:
    result = source['execution_result']
    _validate_export_structure(source, result)
    for field in ('control_plane_evidence', 'rejected_observations'):
        if field not in source:
            raise ImportContractError('producer 2.0.0 missing ' + field)
    evidence = _obj(source['control_plane_evidence'], 'control_plane_evidence')
    if result.get('control_plane_evidence', {}) != evidence:  # absent equals empty (optional member)
        raise ImportContractError('result Control Plane evidence differs from export')
    observation = result.get('observation')
    kind = _observation_kind(observation)
    _validate_export_layout(source, observation, kind)
    _validate_result_contract(result, observation, kind)
    _validate_result_attempt_binding(source, result)
    if kind == "recovery":
        _validate_recovery_observation(observation, result, effect, op)
    elif kind == "none":
        # Strict null-observation rule (owner decision 2026-10-17, contract item 15): with no observation nothing was
        # established, so observed_state is 'unknown' for every result status.
        if result.get('observed_state') != 'unknown':
            raise ImportContractError('null observation cannot establish observed state',
                                      "null_observation_state_mismatch")
    elif kind == "validated":
        if (result.get('status') == 'unknown' and observation.get('state') in {'applied', 'partial'}
                and ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATION):
            raise ImportContractError("an unknown result cannot carry a validated applied/partial observation",
                                      "unknown_with_validated_observation")
        if result.get('observed_state') != observation.get('state'):
            if result.get('status') == 'unknown':
                raise ImportContractError('unknown result observed-state contradiction with its validated observation',
                                          "unknown_state_mismatch")
            raise ImportContractError('execution observed-state contradiction')
        _validate_observation_content(observation, effect, op, 'execution_result.observation')
        if observation.get('state') in {'applied', 'partial'}:
            _accepted_repaired_observation(observation, effect)
    problems = _result_matrix_problems(result)
    if problems:
        raise ImportContractError("the producer status matrix contradicts the execution result: " + "; ".join(problems),
                                  "result_state_matrix")
    if observation is None and result.get('attempted') and result.get('status') != 'unknown':
        raise ImportContractError('attempt without validated observation must remain unknown')
    if result.get('newly_executed') and not source.get('effects'):
        raise ImportContractError('new effect claim lacks retained destination row')
    if result.get('observed_state') in {'applied', 'partial'}:
        if not source.get('effects') or any(row.get('state') != result['observed_state'] for row in source['effects']):
            raise ImportContractError('observed state contradicts retained destination state')
    cp_observations = [r.data for r in cp_records if r.record_type == 'effect_observation']
    # Do not weaken operation binding for accepted upstream observations.
    for item in cp_observations:
        _validate_observation_content(item, effect, op, 'control_plane.observations')
    route_b_members: set[str] = set()
    if any(r.producer_profile_id in {BOUNDED_REFUSAL_PROFILE, BOUNDED_RUNTIME_AUTHORITY_PROFILE, *SECURITY_RUNTIME_BOUNDED_PROFILES} for r in cp_records):
        allowed = {'attempt', 'reconciliation', 'refusal'}
        security = any(r.producer_profile_id in SECURITY_RUNTIME_BOUNDED_PROFILES for r in cp_records)
        if security:
            allowed.add('failure_record_id')
        recovery_report = bool(observation) and _is_recovery_observation(observation)
        if recovery_report:
            # Route B post-commit failure: the executor names the failure it recorded (reference only).
            allowed |= {'failure_record_id', 'failure_class'}
        route_b_members = set(evidence) & ROUTE_B_EXECUTION_EVIDENCE_MEMBERS
        if route_b_members:
            # Route B (atomic local authority) normal execution: the executor names the claim and the local authority
            # receipt it linearized under. The members are descriptive evidence of the destination's own authority check;
            # they are bound to this result by identity and never establish more than the validated observation does.
            _validate_route_b_execution_evidence(evidence, result, effect, source['execution_envelope']['decision_id'], op)
            allowed |= ROUTE_B_EXECUTION_EVIDENCE_MEMBERS
        if set(evidence) - allowed:
            raise ImportContractError('unsupported typed refusal executor evidence field')
        # This identifier is an attributable reference only. No failure row is
        # exported by this producer, so it cannot establish independent durability.
        if 'failure_record_id' in evidence:
            reference = evidence['failure_record_id']
            if recovery_report:
                invalid = (not isinstance(reference, str) or not reference or len(reference) > 200
                           or result.get('status') != 'unknown' or result.get('acknowledged')
                           or result.get('newly_executed'))
            else:
                invalid = (not isinstance(reference, str) or not reference or len(reference) > 200
                           or result.get('status') != 'denied' or result.get('attempted')
                           or result.get('acknowledged') or result.get('newly_executed'))
            if invalid:
                raise ImportContractError('invalid nonauthorizing executor failure reference')
        if 'failure_class' in evidence:
            failure_class = evidence['failure_class']
            if not isinstance(failure_class, str) or not failure_class or len(failure_class) > 100:
                raise ImportContractError('invalid executor failure class')
        refusal = evidence.get('refusal')
        did = source['execution_envelope']['decision_id']
        retained = [r.data for r in cp_records if r.record_type == 'effect_time_refusal' and r.data.get('decision_id') == did and r.data.get('effect_id') == effect]
        if refusal is not None:
            if refusal not in retained or result.get('status') != 'denied' or result.get('attempted') or result.get('newly_executed') or result.get('acknowledged'):
                raise ImportContractError('executor refusal lacks matching denied durable lineage')
        elif retained and result.get('status') == 'denied':
            raise ImportContractError('executor dropped retained typed refusal')
    rec = evidence.get('reconciliation')
    attempt = evidence.get('attempt')
    supplied_attempts = source.get('control_plane_attempts')  # optional member of the lifecycle contract
    if supplied_attempts is not None and supplied_attempts != ([attempt] if attempt else []):
        raise ImportContractError('Control Plane attempts differ from result owning evidence')
    if rec is not None:
        rec = _obj(rec, 'executor reconciliation')
        if rec.get('effect_id') != effect:
            raise ImportContractError('enclosing reconciliation effect identity mismatch')
        retained = [r.data for r in cp_records if r.record_type == 'reconciliation']
        if rec not in retained:
            raise ImportContractError('executor reconciliation has no matching retained Control Plane record')
        if rec.get('retry_eligible') is not False:
            raise ImportContractError('unsupported retry eligibility')
        rejected = [rec['observation']] if not rec['observation_accepted'] and rec.get('observation') is not None else []
        if source['rejected_observations'] != rejected:
            raise ImportContractError('rejected observations differ from retained reconciliation')
        if observation and (not rec['observation_accepted'] or rec.get('observation') != observation):
            raise ImportContractError('rejected/substituted evidence promoted to accepted observation')
        if result.get('attempted') and rec['observation_accepted'] and observation != rec.get('observation'):
            raise ImportContractError('accepted reconciliation observation missing from attempted result')
        if not rec['observation_accepted'] and result.get('observed_state') != 'unknown':
            raise ImportContractError('rejected observation cannot establish observed state')
    elif source['rejected_observations']:
        raise ImportContractError('rejected evidence has no enclosing reconciliation')
    if result.get('attempted') and not (attempt is None and rec is None and result.get('attempt_id')
                                        and (_is_recovery_observation(observation) or route_b_members)):
        # (A route B atomic-local execution has no Control Plane attempt or reconciliation; its recovery
        # report stands in for them and is retained as a report only, and a normal execution is described by its
        # validated local authority receipt, which is bound to the result above.)
        if not attempt or rec is None or not result.get('attempt_id'):
            raise ImportContractError('attempted execution lacks owning attempt/reconciliation')
    elif not result.get('attempted') and (result.get('acknowledged') or result.get('newly_executed')):
        raise ImportContractError('non-attempted result cannot acknowledge or execute')
    if result.get('status') == 'observed' and evidence:
        raise ImportContractError('historical local observation cannot claim CP validation')
    if attempt:
        did = source['execution_envelope']['decision_id']
        if attempt.get('effect_id') != effect or attempt.get('decision_id') != did:
            raise ImportContractError('Control Plane attempt enclosing identity mismatch')
        owner = [r.data for r in cp_records if r.record_type == 'control_plane_attempt_transition']
        if attempt not in owner:
            raise ImportContractError('attempt has no matching owning Control Plane record')
        primary = source.get('attempt_identity') or {}
        ack = attempt.get('acknowledgement') or {}
        if primary.get('namespace') == 'executor':
            if ack.get('attempt_id') is not None and ack['attempt_id'] != primary.get('attempt_id'):
                raise ImportContractError('acknowledgement executor attempt mismatch')
            if result.get('acknowledged') and ack.get('attempt_id') != result.get('attempt_id'):
                raise ImportContractError('acknowledged executor result lacks explicit attempt link')
        elif primary.get('namespace') == 'control_plane' and primary.get('attempt_id') != attempt.get('attempt_id'):
            raise ImportContractError('primary Control Plane attempt identity mismatch')
        if result.get('acknowledged') != (attempt.get('status') in {'acknowledged', 'partial'}):
            # A reconciled partial result has no acknowledgement in the executor's
            # public mapping, despite the retained CP partial lifecycle status.
            if not (primary.get('namespace') == 'control_plane' and attempt.get('status') == 'partial' and result.get('acknowledged') is False):
                raise ImportContractError('acknowledgement claim contradicts owning attempt')
        if result.get('newly_executed') and ack.get('newly_executed') is not True:
            raise ImportContractError('new effect claim lacks producer acknowledgement')
        if (primary.get('namespace') == 'executor' and ack.get('newly_executed') is True
                and not result.get('newly_executed')):
            raise ImportContractError('producer acknowledgement of a new effect contradicts the execution result')


def _effect_observation_history(cp: dict[str, Any]) -> dict[str, Any]:
    """Summarize each effect using only its owning producer's array order.

    Reconciliations and attempts are independent sequences, not a merged clock.
    No latest-at-import-time claim or ordering of historical local observations
    relative to Control Plane observations is established.
    """
    effects = {}
    for decision in cp["decisions"]:
        effect = decision.get("effect_id")
        if effect is not None:
            effects.setdefault(effect, {
                "basis": "Control Plane reconciliation array order, filtered by exact effect_id",
                "rejected_reconciliation_indices": [],
                "latest_reconciliation": None,
                "latest_accepted_observation": None,
                "latest_supported_destination_state": "unknown",
                "retry_eligible": None,
                "acknowledgement_history": [],
                "cross_sequence_order": "not_established",
                "freshness_at_import": "not_evaluated",
            })
    for index, rec in enumerate(cp["reconciliations"]):
        value = effects[rec["effect_id"]]
        value["latest_reconciliation"] = {
            "source_index": index, "result": rec["result"],
            "observation_accepted": rec["observation_accepted"],
        }
        value["retry_eligible"] = rec["retry_eligible"]
        if rec["observation_accepted"]:
            value["latest_accepted_observation"] = {
                "source_index": index, "observation": rec["observation"],
            }
            value["latest_supported_destination_state"] = rec["observation"]["state"]
        else:
            value["rejected_reconciliation_indices"].append(index)
            # An older accepted observation is retained separately; a subsequent
            # rejected observation does not establish current destination state.
            value["latest_supported_destination_state"] = "unknown"
    for index, attempt in enumerate(cp["attempts"]):
        effects[attempt["effect_id"]]["acknowledgement_history"].append({
            "source_index": index, "attempt_id": attempt["attempt_id"],
            "status": attempt["status"],
            "acknowledgement": attempt.get("acknowledgement"),
        })
    return effects
