"""Regenerate the strict-tenant / legacy-tenant SECURITY-RUNTIME shape Control Plane run records in this directory from REAL Control Plane code (no hand editing).

Developer tool, never run by the test suite:
    PYTHONPATH=<cp-checkout>/src:<cp-checkout> python generate_from_cp.py <cp-checkout> <out-dir>

Source: cogno-us/cognous-control-plane at 484fdbd297235dd24148ddb0703f2055a31eabff (CP-2 merged, #109). It drives that checkout's own test helpers
(tests/test_runtime_authority.py setup_flow, bind_approval and tests/test_bounded_authorization.py tenant_proposal / tenant_resolver_for) with a TENANT-aware
proposal and a runtime-authority profile (so the persisted run carries the programme-2 journal members), decides, and executes once with the Control Plane's
own local refund destination. Each case is persisted through the Control Plane's own BoundedRecordStore.
  strict : default tenant_binding_generation (bounded-authorization-effect/0.3-strict-tenant)
  legacy : explicit tenant_binding_generation=bounded-authorization-effect/0.2
Synthetic data only. Not independent qualification.
"""
import json
import sys
import tempfile
from pathlib import Path

cp_root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(cp_root / "src"), str(cp_root)]

import agent_control_plane.bounded as B  # noqa: E402
from agent_control_plane.bounded import BoundedAuthorizationWorkflow, BoundedRecordStore, LocalRefundDestination, ObservationPolicy, commitment  # noqa: E402
from agent_control_plane.runtime_authority import ActionClass, RuntimeAuthorityProfile  # noqa: E402
from tests import test_bounded_authorization as T  # noqa: E402
from tests import test_runtime_authority as R  # noqa: E402

B._now = lambda: T.NOW
out.mkdir(parents=True, exist_ok=True)
vectors = {}
for name, generation in (("strict", B.TENANT_GENERATION_STRICT), ("legacy", B.TENANT_GENERATION_LEGACY)):
    work = Path(tempfile.mkdtemp(prefix=f"r3-{name}-"))
    p = T.tenant_proposal()
    r = T.tenant_resolver_for(p)
    cl = ActionClass(class_id="synthetic-irreversible", irreversible=True, max_status_age_seconds=60, on_unreadable="refuse")
    cfg = RuntimeAuthorityProfile(catalogue_version="synthetic-catalogue/1", actions={p.action_id: cl}, producer_keys={"synthetic-validator": R.PUBLIC},
                                  allow_synthetic_resolver=True)
    base = T.workflow(work / "baseline", p, resolver=r, tenant_binding_generation=generation).decide(p, now=T.NOW)
    required = sorted([{"input_type": x.input_type, "input_id": x.input_id} for x in base.resolution_inputs], key=lambda x: (x["input_type"], x["input_id"]))
    context = r.contexts[T.PROFILE]
    criteria = {}
    for ob in context["requirement"]["evidence"]:
        if ob["required"] and ob["kind"] == "authorization":
            criteria[ob["obligation_id"]] = {"kind": "exact_members", "producer_id": "synthetic-validator", "subject_digest": commitment(R.MEMBERS),
                                             "minimum_count": 40, "members": R.MEMBERS}
            R.sign_evidence(r.evidence[ob["obligation_id"]], tenant_id=T.TENANT)
    context["runtime_authority"] = {"profile": "runtime-authority/0.1", "required_inputs": required, "required_inputs_digest": commitment(required), "evidence_criteria": criteria}
    R.bind_approval(r, cfg)
    f = BoundedAuthorizationWorkflow(manifest=T.manifest(), resolver=r, destination=LocalRefundDestination(work / "destination.json"),
                                     records=BoundedRecordStore(work / "run.json", "run-1"), observation_policy=ObservationPolicy(max_age_seconds=300),
                                     allow_test_time=True, runtime_authority_profile=cfg, tenant_binding_generation=generation)
    d = f.decide(p, now=T.NOW)
    assert d.result == "authorized", d.reasons
    a, o = f.execute(p, d, adapter_id=p.adapter_id, now=T.NOW)
    assert a.status == "acknowledged" and o.state == "applied"
    BoundedRecordStore(work / "run.json", "run-1").load()  # the CP's own validating retrieval
    run = json.loads((work / "run.json").read_bytes())
    d0 = run["decisions"][0]
    assert d0["effect_id"] == f._effect_id(d.binding)
    (out / f"{name}_control_plane_run.json").write_text(json.dumps(run, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out / f"{name}_proposal.json").write_text(json.dumps(json.loads(p.model_dump_json()), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    b = d0["binding"]
    vectors[name] = {"proposal": b["proposal_commitment"], "grant_id": b["grant_id"], "grant_revision": b["grant_revision"], "generation": b["generation"],
                     "tenant_id": b["tenant_id"], "effect_id": d0["effect_id"]}
(out / "vectors.json").write_text(json.dumps(vectors, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(vectors, indent=1))
