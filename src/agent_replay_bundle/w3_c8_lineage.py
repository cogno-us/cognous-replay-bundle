"""C8 source-record reconstruction. Never authorizes effects."""
from __future__ import annotations
from .reconstruction import ReconstructionBundle,ProducerProfile,SourceRecord,ImportReport,ImportFinding

class C8LineageError(ValueError):
    pass

ORDER=("stop_requested","stop_acknowledged","dispatch_closed",
       "quiescence_observed","destination_reconciled")

def import_c8_source(*, authority:dict,stop:dict|None=None) -> ReconstructionBundle:
    if authority.get("generation")!="c8-source-rows/0.1":
        raise C8LineageError("unsupported authority export")
    rows=authority.get("rows")
    if not isinstance(rows,dict):
        raise C8LineageError("authority rows missing")
    claims=rows.get("execution_claims_v1",[])
    if len(claims)>1:
        raise C8LineageError("ambiguous claim")
    if claims and claims[0].get("claim_id")!=authority.get("claim_id"):
        raise C8LineageError("claim identity mismatch")
    tenant=claims[0].get("tenant_id") if claims else None
    grant=claims[0].get("grant_id") if claims else None
    for name in ("authority_grants_v1","authority_approvals_v1","authority_policies_v1"):
        if name not in rows and claims:
            raise C8LineageError("source table absent: "+name)
        for x in rows.get(name,[]):
            if not isinstance(x,dict):
                raise C8LineageError("source row not object")
            if x.get("tenant_id")!=tenant:
                raise C8LineageError("tenant mismatch in "+name)
            if name in ("authority_grants_v1","authority_approvals_v1") and x.get("grant_id")!=grant:
                raise C8LineageError("grant mismatch in "+name)
    if claims:
        try:
            import json
            from .ingress import check_depth,MAX_NESTING_DEPTH
            check_depth(claims[0]["claim_json"],MAX_NESTING_DEPTH)
            raw=json.loads(claims[0]["claim_json"])
        except (KeyError,TypeError,ValueError,RecursionError):
            raise C8LineageError("retained claim JSON unavailable or corrupt")
        if raw.get("claim_id")!=authority["claim_id"] or raw.get("tenant_id")!=tenant:
            raise C8LineageError("retained claim JSON identity contradiction")
        if raw.get("grant_id")!=grant or str(raw.get("grant_revision"))!=str(claims[0].get("grant_revision")):
            raise C8LineageError("grant revision contradiction")
        if not raw.get("operation_commitment"):
            raise C8LineageError("retained operation commitment absent")
        grant_rows=rows.get("authority_grants_v1",[])
        if grant_rows and str(grant_rows[0].get("revision"))!=str(claims[0].get("grant_revision")):
            raise C8LineageError("authoritative grant revision mismatch")
        expected_approvals={x.get("approval_ref") for x in raw.get("approval_state",[])}
        available_approvals={x.get("approval_ref") for x in rows.get("authority_approvals_v1",[])}
        if not expected_approvals.issubset(available_approvals):
            raise C8LineageError("required approval row unavailable")
        proposal_commitments={a.get("proposal_commitment") for a in rows.get("authority_approvals_v1",[])}
        if any(not isinstance(x,str) or not x for x in proposal_commitments):
            raise C8LineageError("retained approval proposal commitment absent")
        if len(proposal_commitments)>1:
            raise C8LineageError("conflicting approval proposal commitments")
        expected_policies={(x.get("ref"),str(x.get("version"))) for x in raw.get("policy_state",[])}
        actual_policies={(x.get("ref"),str(x.get("version"))) for x in rows.get("authority_policies_v1",[])}
        if not expected_policies.issubset(actual_policies):
            raise C8LineageError("required policy revision unavailable")
    events=[]
    if stop is not None:
        if stop.get("generation")!="c8-local-stop/0.1":
            raise C8LineageError("unsupported stop generation")
        events=stop.get("events")
        if not isinstance(events,list):
            raise C8LineageError("stop events absent")
        seen=set();previous=-1;previous_order=-1;effect=None
        for item in events:
            if not isinstance(item,dict):
                raise C8LineageError("stop record invalid")
            eid=item.get("event_id");seq=item.get("sequence");kind=item.get("kind")
            if not isinstance(eid,str) or not eid or eid in seen:
                raise C8LineageError("duplicate stop event identity")
            if not isinstance(seq,int) or seq<=previous or kind not in ORDER:
                raise C8LineageError("stop sequence invalid")
            order=ORDER.index(kind)
            if order<=previous_order:
                raise C8LineageError("stop lifecycle out of order")
            if item.get("lifecycle_id")!=stop.get("lifecycle_id"):
                raise C8LineageError("stop lifecycle mismatch")
            effect=effect or item.get("effect_id")
            if not effect or effect!=item.get("effect_id"):
                raise C8LineageError("cross-effect stop identity")
            seen.add(eid);previous=seq;previous_order=order
    records=[]
    profile="c8-retained-sqlite-and-explicit-stop/0.1"
    for table,items in rows.items():
        if not isinstance(items,list):
            raise C8LineageError("table rows not array")
        for i,item in enumerate(items):
            records.append(SourceRecord(record_id=f"{profile}:{table}:{i}",producer_profile_id=profile,
                record_type=table,source_sequence=len(records),source_path=f"authority.rows.{table}[{i}]",
                identifiers={k:str(v) for k,v in item.items() if k in (
                    "claim_id","grant_id","approval_ref","ref","tenant_id") and v is not None},
                data=item))
    for i,item in enumerate(events):
        records.append(SourceRecord(record_id=f"{profile}:stop:{i}",producer_profile_id=profile,
            record_type="local_stop_event",source_sequence=len(records),
            source_path=f"stop.events[{i}]",identifiers={
                "event_id":item["event_id"],"lifecycle_id":item["lifecycle_id"],
                "effect_id":item["effect_id"]},data=item))
    findings=[]
    if not claims:
        findings.append(ImportFinding(code="C8-CLAIM",category="missing_dependency",
             severity="warning",path="authority.rows.execution_claims_v1",
             message="No retained claim; no tenant or authorization inferred.",value_state="unavailable"))
    if claims and (not tenant or not rows.get("authority_grants_v1") or
                   not rows.get("authority_approvals_v1") or not rows.get("authority_policies_v1")):
        findings.append(ImportFinding(code="C8-AUTH",category="missing_dependency",
             severity="warning",path="authority.rows",
             message="Tenant or authority record missing; lineage incomplete.",
             value_state="unavailable"))
    if stop is None or [x["kind"] for x in events]!=list(ORDER):
        findings.append(ImportFinding(code="C8-STOP",category="missing_dependency",
             severity="warning",path="stop.events",message="Stop lifecycle incomplete or unavailable; no quiescence inferred.",
             value_state="unavailable"))
    return ReconstructionBundle(status="reconstruction_partial" if findings else "reconstruction_complete",
        producer_profiles=[ProducerProfile(profile_id=profile,producer="Cognous local retained source rows",
          repository="cogno-us/cognous-execution-runtime",revision="candidate-c8",
          format_name="source-rows-plus-explicit-events",format_version="0.1")],
        records=records,import_reports=[ImportReport(adapter_profile=profile,
          source_revision="candidate-c8",complete=not findings,findings=findings)],
        metadata={"source_export_claim_id":authority.get("claim_id"),
                  "source_asserted_tenant":tenant,"non_authorizing":True,
                  "source_revision_not_independently_verified":True})
