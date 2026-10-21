"""W3 bounded atomic failure-history projection (C4/C5/C7).

Consumes only explicitly exported producer records from the accepted W2 Runtime
revision. This is not the legacy bounded-workflow importer and cannot authorize
or replay an effect. Caller is responsible for acquiring actual durable records.
"""
from __future__ import annotations

from typing import Any

from .reconstruction import (
    ImportFinding, ImportReport, ProducerProfile, ReconstructionBundle,
    SourceRecord, RecordLink,
)

W2_RUNTIME_REVISION = "bd398f16c4cee329d2d0213afc3236ca9232d29e"
W2_ATOMIC_PROFILE = "local-atomic-w2-failure-history@bd398f16"
W2_FAILURE_FORMAT = "failure_records_v1"
_ALLOWED_CLASSES = {"policy_denial", "authority_hold", "evaluation_error", "dispatch_error"}
_ALLOWED_STAGES = {"pre_dispatch", "post_dispatch"}


class AtomicEvidenceContractError(ValueError):
    """Incompatible or contradictory retained atomic producer evidence."""


def import_w2_atomic_failure_history(
    *, runtime_revision: str, effect_id: str, decision_id: str,
    failure_records: list[dict[str, Any]],
    attempt_records: list[dict[str, Any]] | None = None,
    observation: dict[str, Any] | None = None,
    tenant_id: str | None = None,
) -> ReconstructionBundle:
    """Import retained W2 rows without inventing missing attempts or observations.

    This auxiliary projection does NOT claim to verify the source revision,
    tenant binding, grant, effect or destination. Those require independent
    producer acquisition and the normal dispatch authorization boundary.
    """
    if runtime_revision != W2_RUNTIME_REVISION:
        raise AtomicEvidenceContractError("unsupported exact W2 Runtime revision")
    if not all(isinstance(s, str) and s for s in (effect_id, decision_id)):
        raise AtomicEvidenceContractError("effect_id and decision_id required")
    if not isinstance(failure_records, list):
        raise AtomicEvidenceContractError("failure_records must be an array")
    if attempt_records is not None and not isinstance(attempt_records, list):
        raise AtomicEvidenceContractError("attempt_records must be an array")
    records: list[SourceRecord] = []
    links: list[RecordLink] = []
    report = ImportReport(
        adapter_profile=W2_ATOMIC_PROFILE, source_revision=W2_RUNTIME_REVISION,
        complete=True, field_mappings={
            "failure_records_v1": "records[atomic_failure]",
            "attempt_records": "records[atomic_attempt]",
            "observation": "records[atomic_observation]",
        },
    )
    ids: set[str] = set()
    attempts: dict[str, str] = {}
    if attempt_records is not None:
        for index, row in enumerate(attempt_records):
            if not isinstance(row, dict):
                raise AtomicEvidenceContractError("attempt record must be object")
            aid = row.get("attempt_id")
            if not isinstance(aid, str) or not aid or aid in attempts:
                raise AtomicEvidenceContractError("duplicate or missing attempt identity")
            if row.get("effect_id") != effect_id or row.get("decision_id") != decision_id:
                raise AtomicEvidenceContractError("attempt effect/decision lineage contradiction")
            rid = f"{W2_ATOMIC_PROFILE}:attempt:{index}"
            attempts[aid] = rid
            records.append(SourceRecord(
                record_id=rid, producer_profile_id=W2_ATOMIC_PROFILE,
                record_type="atomic_attempt", source_sequence=len(records),
                source_path=f"attempt_records[{index}]",
                identifiers={"effect_id":effect_id, "decision_id":decision_id, "attempt_id":aid},
                data=row,
            ))
    else:
        report.complete = False
        report.findings.append(ImportFinding(code="W3A01",category="missing_dependency",
            severity="warning",path="attempt_records",
            message="Authoritative attempt-history rows not supplied; no attempt may be inferred.",
            value_state="unavailable"))
    for index, row in enumerate(failure_records):
        if not isinstance(row, dict):
            raise AtomicEvidenceContractError("failure record must be object")
        fid = row.get("failure_id")
        if not isinstance(fid, str) or not fid or fid in ids:
            raise AtomicEvidenceContractError("duplicate or missing failure identity")
        ids.add(fid)
        if row.get("effect_id") != effect_id or row.get("decision_id") != decision_id:
            raise AtomicEvidenceContractError("failure effect/decision lineage contradiction")
        klass, stage, aid = row.get("failure_class"), row.get("stage"), row.get("attempt_id")
        if klass not in _ALLOWED_CLASSES or stage not in _ALLOWED_STAGES:
            raise AtomicEvidenceContractError("unsupported failure class or stage")
        if not isinstance(row.get("reason_code"), str) or not row["reason_code"]:
            raise AtomicEvidenceContractError("failure reason_code required")
        if stage == "pre_dispatch" and aid is not None:
            raise AtomicEvidenceContractError("pre-dispatch failure cannot own an execution attempt")
        if stage == "post_dispatch" and (not isinstance(aid, str) or not aid):
            raise AtomicEvidenceContractError("post-dispatch failure requires real attempt identity")
        if aid is not None and attempt_records is not None and aid not in attempts:
            raise AtomicEvidenceContractError("failure refers to missing owning attempt")
        rid=f"{W2_ATOMIC_PROFILE}:failure:{index}"
        records.append(SourceRecord(
            record_id=rid, producer_profile_id=W2_ATOMIC_PROFILE,
            record_type="atomic_failure", source_sequence=len(records),
            source_path=f"failure_records_v1[{index}]",
            identifiers={k:v for k,v in {"failure_id":fid, "effect_id":effect_id,
                "decision_id":decision_id,"attempt_id":aid}.items() if v is not None},
            data=row,
        ))
        if aid is not None and aid in attempts:
            links.append(RecordLink(link_type="explicit",from_record_id=rid,
                to_record_id=attempts[aid],basis="failure_records_v1.attempt_id",
                establishes_identity_equivalence=False))
        elif aid is not None:
            report.complete=False
            report.findings.append(ImportFinding(code="W3A02",category="missing_dependency",
                severity="warning",path=f"failure_records_v1[{index}].attempt_id",
                message="Attempt ID retained; matching durable attempt row not supplied.",
                value_state="unavailable"))
    if observation is None:
        report.complete=False
        report.findings.append(ImportFinding(code="W3A03",category="missing_dependency",
            severity="warning",path="observation",
            message="Authoritative observation unavailable; no completion inferred.",
            value_state="unavailable"))
    else:
        if not isinstance(observation,dict):
            raise AtomicEvidenceContractError("observation must be object")
        if "effect_id" in observation and observation["effect_id"] != effect_id:
            raise AtomicEvidenceContractError("observation effect identity contradiction")
        if "retry_eligible" in observation and observation["retry_eligible"] is not False:
            raise AtomicEvidenceContractError("atomic W2 evidence cannot grant retry authority")
        records.append(SourceRecord(
            record_id=f"{W2_ATOMIC_PROFILE}:observation:0",
            producer_profile_id=W2_ATOMIC_PROFILE,
            record_type="atomic_observation",source_sequence=len(records),
            source_path="observation",
            identifiers={"effect_id":effect_id,"decision_id":decision_id},
            data=observation,
        ))
    if tenant_id is not None:
        report.complete=False
        report.findings.append(ImportFinding(code="W3A04",category="unsupported_semantic",
            severity="warning",path="tenant_id",
            message="Caller-supplied tenant is context only; this projection does not verify tenant authorization."))
    return ReconstructionBundle(
        status="reconstruction_complete" if report.complete else "reconstruction_partial",
        producer_profiles=[ProducerProfile(profile_id=W2_ATOMIC_PROFILE,
            producer="Cognous Execution Runtime local atomic W2",
            repository="cogno-us/cognous-execution-runtime",
            revision=W2_RUNTIME_REVISION,format_name=W2_FAILURE_FORMAT,
            format_version="1")],
        records=records,links=links,import_reports=[report],
        metadata={"effect_id":effect_id,"decision_id":decision_id,
            "tenant_context_source_asserted":tenant_id,
            "non_authorizing":True,
            "source_revision_is_caller_asserted":True},
    )
