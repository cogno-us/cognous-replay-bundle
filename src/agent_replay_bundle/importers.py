"""Revision-pinned producer import adapters."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

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
CONTROL_PLANE_SUPPORTED_V2_REVISIONS = (*CONTROL_PLANE_V2_REVISIONS, CONTROL_PLANE_MERGED_REVISION, CONTROL_PLANE_REFUSAL_REVISION, CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, CONTROL_PLANE_SECURITY_REVISION)
MOLTBOT_V2_REVISION = "177354e959cc78c59c1a776f018cfbfbf28c927b"
BOUNDED_V2_PROFILE = "control-plane-bounded-run@2ea9528e"
BOUNDED_V2_PERSISTENCE_PROFILE = "control-plane-bounded-run@248d8996"
MOLTBOT_V2_PROFILE = "moltbot-safe-executor-producer-2.0.0@177354e9"
PRODUCER_COMPATIBILITY = {
    "1.0.0": (MOLTBOT_SAFE_REVISION, CONTROL_PLANE_REVISION, MOLTBOT_PROFILE),
    "2.0.0": (MOLTBOT_V2_REVISION, CONTROL_PLANE_V2_REVISION, MOLTBOT_V2_PROFILE),
}


class ImportContractError(ValueError):
    """Producer data violates the pinned import contract."""


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
                    label: str) -> None:
    old = seen.get(key)
    if old is None:
        seen[key] = value
    elif old != value:
        raise ImportContractError(f"conflicting content under immutable {label} {key}")


def _require_equal(actual: Any, expected: Any, path: str) -> None:
    if actual != expected:
        raise ImportContractError(f"{path} conflicts with committed operation")


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
    try:
        decoded = __import__("json").loads(value)
    except (TypeError, ValueError) as exc:
        raise ImportContractError(f"{path} is invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ImportContractError(f"{path} must decode to an object")
    return decoded


def _validate_observation_content(observation: dict[str, Any], effect_id: str, op: dict[str, Any], path: str) -> None:
    _require_equal(observation.get("effect_id"), effect_id, path + ".effect_id")
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
    repaired = control_plane_revision in CONTROL_PLANE_SUPPORTED_V2_REVISIONS
    bounded_profile = {
        CONTROL_PLANE_V2_REVISION: BOUNDED_V2_PROFILE,
        CONTROL_PLANE_V2_PERSISTENCE_REVISION: BOUNDED_V2_PERSISTENCE_PROFILE,
        CONTROL_PLANE_MERGED_REVISION: BOUNDED_MERGED_PROFILE,
        CONTROL_PLANE_REFUSAL_REVISION: BOUNDED_REFUSAL_PROFILE,
        CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION: BOUNDED_RUNTIME_AUTHORITY_PROFILE,
        CONTROL_PLANE_SECURITY_REVISION: BOUNDED_SECURITY_PROFILE,
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
    if repaired:
        _validate_repaired_run(cp)
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
    authority = control_plane_revision in {CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, CONTROL_PLANE_SECURITY_REVISION}
    extended = control_plane_revision in {CONTROL_PLANE_REFUSAL_REVISION, CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, CONTROL_PLANE_SECURITY_REVISION}
    if extended:
        from .refusal_evidence import EXTENDED, AUTHORITY_EXTENDED, validate_run
        EXTENDED = {**EXTENDED, **AUTHORITY_EXTENDED} if authority else EXTENDED
        if authority:
            cp = dict(cp)
            cp.setdefault("vocabulary_changes", [])
        unfinished = validate_run(cp, proposal, runtime_authority=authority)
        report.field_mappings.update({field: "records["+kind+"]" for field,kind in EXTENDED.items()})
        for check_id in unfinished:
            report.complete = False
            report.findings.append(ImportFinding(
                code="B006", category="value_state", severity="warning", path="check_events",
                message=f"Resolution journal check {check_id} is opened-only or interrupted; its authority evaluation did not complete.",
                value_state="unknown",
            ))
    for field in sorted(set(cp) - required - (set(EXTENDED) if extended else set())):
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
        _unique_or_same(attempt_invariants, aid, invariant, "attempt_id")
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
            "manifest_revision": MANIFEST_SECURITY_REVISION if control_plane_revision == CONTROL_PLANE_SECURITY_REVISION else MANIFEST_REVISION,
            **({"executor_failure_reference_verification": "source_asserted_not_independently_verified"} if control_plane_revision == CONTROL_PLANE_SECURITY_REVISION else {}),
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
        for field in ("attempt_identity", "control_plane_attempts", "observations"):
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
    if result.get("decision_id") != envelope_decision or result.get("effect_id") != envelope_effect:
        raise ImportContractError("Moltbot execution_result identifiers do not match execution envelope")
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
    if isinstance(result_observation, dict) and result_observation:
        _require_equal(result_observation.get("effect_id"), envelope_effect, "execution_result.observation.effect_id")
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
        digest = raw.get("operation_digest")
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

    for i, raw in enumerate(source.get("observations") or []):
        raw = _obj(raw, f"moltbot.observations[{i}]")
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
                if profile_id == MOLTBOT_V2_PROFILE:
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
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError('timezone missing')
        return result
    except (ValueError, AttributeError, TypeError) as exc:
        raise ImportContractError('accepted observation requires timezone-aware times') from exc


def _validate_repaired_run(cp: dict[str, Any]) -> None:
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
        age = (_aware_time(rec.get('evaluation_time')) - _aware_time(observation.get('observed_at'))).total_seconds()
        if age > maximum or age < -tolerance:
            raise ImportContractError('accepted observation violates recorded temporal policy')
        expected = {'applied': 'applied', 'absent': 'observed_absent', 'partial': 'hold'}[observation['state']]
        if rec.get('result') != expected:
            raise ImportContractError('reconciliation result contradicts accepted observation')
        accepted.append(observation)
    if cp.get('observations') != accepted:
        raise ImportContractError('accepted Control Plane observations differ from retained reconciliations')
    terminal = {}
    for attempt in cp.get('attempts', []):
        if attempt.get('status') != 'attempted':
            _unique_or_same(terminal, attempt.get('attempt_id'), attempt, 'terminal Control Plane attempt')


def _validate_v2_export(source: dict[str, Any], cp_records: list[SourceRecord],
                        op: dict[str, Any], effect: str) -> None:
    result = source['execution_result']
    for field in ('control_plane_evidence', 'rejected_observations', 'observations'):
        if field not in source:
            raise ImportContractError('producer 2.0.0 missing ' + field)
    evidence = _obj(source['control_plane_evidence'], 'control_plane_evidence')
    if result.get('control_plane_evidence') != evidence:
        raise ImportContractError('result Control Plane evidence differs from export')
    observation = result.get('observation')
    if observation is not None and not isinstance(observation, dict):
        raise ImportContractError('execution observation must be object or null')
    expected_observations = [observation] if observation else []
    if source['observations'] != expected_observations:
        raise ImportContractError('accepted executor observations differ from result')
    if not observation and result.get('observed_state') != 'unknown':
        raise ImportContractError('null observation cannot establish observed state')
    if observation:
        if result.get('observed_state') != observation.get('state'):
            raise ImportContractError('execution observed-state contradiction')
        _validate_observation_content(observation, effect, op, 'execution_result.observation')
        if observation.get('state') in {'applied', 'partial'}:
            _accepted_repaired_observation(observation, effect)
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
    if any(r.producer_profile_id in {BOUNDED_REFUSAL_PROFILE, BOUNDED_RUNTIME_AUTHORITY_PROFILE, BOUNDED_SECURITY_PROFILE} for r in cp_records):
        allowed = {'attempt', 'reconciliation', 'refusal'}
        security = any(r.producer_profile_id == BOUNDED_SECURITY_PROFILE for r in cp_records)
        if security:
            allowed.add('failure_record_id')
        if set(evidence) - allowed:
            raise ImportContractError('unsupported typed refusal executor evidence field')
        # This identifier is an attributable reference only. No failure row is
        # exported by this producer, so it cannot establish independent durability.
        if 'failure_record_id' in evidence:
            reference = evidence['failure_record_id']
            if (not isinstance(reference, str) or not reference or len(reference) > 200
                    or result.get('status') != 'denied' or result.get('attempted')
                    or result.get('acknowledged') or result.get('newly_executed')):
                raise ImportContractError('invalid nonauthorizing executor failure reference')
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
    supplied_attempts = source.get('control_plane_attempts')
    if not isinstance(supplied_attempts, list):
        raise ImportContractError('control_plane_attempts must be an array')
    if supplied_attempts != ([attempt] if attempt else []):
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
    if result.get('attempted'):
        if not attempt or rec is None or not result.get('attempt_id'):
            raise ImportContractError('attempted execution lacks owning attempt/reconciliation')
    elif result.get('acknowledged') or result.get('newly_executed'):
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
