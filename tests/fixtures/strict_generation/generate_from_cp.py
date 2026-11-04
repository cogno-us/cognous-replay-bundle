"""Regenerate the strict / legacy Control Plane fixtures in this directory from REAL Control Plane code (no hand editing).

Usage (developer tool, never run by the test suite):
    PYTHONPATH=<cp-checkout>/src:<cp-checkout> python generate_from_cp.py <cp-checkout> <out-dir>

Source: cogno-us/cognous-control-plane PR #109 (CP-2) head 5bff525a8e08139e02873b409053830f42969006. It drives that checkout's own test fixtures
(tests/test_bounded_authorization.py + tests/test_strict_tenant_generation.py helpers): a tenant-aware ``BoundedAuthorizationWorkflow`` decides one
synthetic tenant proposal, persisting through the Control Plane's own ``BoundedRecordStore`` (run.json), which is re-read through a fresh store.
  strict : default ``tenant_binding_generation`` (bounded-authorization-effect/0.3-strict-tenant)
  legacy : explicit ``tenant_binding_generation=bounded-authorization-effect/0.2``
It also writes ``vectors.json``: proposal commitment, grant_id, grant_revision, generation and the Control Plane ``_effect_id`` for each record.
Synthetic data only. Not independent qualification.
"""
import json
import sys
import tempfile
from pathlib import Path

cp_root, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path[:0] = [str(cp_root / "src"), str(cp_root)]

import agent_control_plane.bounded as B  # noqa: E402
from tests import test_bounded_authorization as T  # noqa: E402

B._now = lambda: T.NOW  # the CP tests' fixed synthetic clock
out.mkdir(parents=True, exist_ok=True)
vectors = {}
for name, generation in (("strict", B.TENANT_GENERATION_STRICT), ("legacy", B.TENANT_GENERATION_LEGACY)):
    work = Path(tempfile.mkdtemp(prefix=f"replay2-{name}-"))
    p = T.tenant_proposal()
    r = T.tenant_resolver_for(p)
    wf = T.workflow(work, p, resolver=r, tenant_binding_generation=generation)
    d = wf.decide(p, now=T.NOW)
    assert d.result == "authorized", d.reasons
    fresh = B.BoundedRecordStore(work / "run.json", "run-1")
    fresh.load()  # the CP's own validating retrieval
    run = json.loads((work / "run.json").read_bytes())
    d0 = run["decisions"][0]
    b = d0["binding"]
    assert d0["effect_id"] == wf._effect_id(d.binding)
    (out / f"{name}_control_plane_run.json").write_text(json.dumps(run, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (out / f"{name}_proposal.json").write_text(json.dumps(json.loads(p.model_dump_json()), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    vectors[name] = {"proposal": b["proposal_commitment"], "grant_id": b["grant_id"], "grant_revision": b["grant_revision"],
                     "generation": b["generation"], "tenant_id": b["tenant_id"], "expected_effect_id": d0["effect_id"],
                     "control_plane_effect_id": wf._effect_id(d.binding)}
(out / "vectors.json").write_text(json.dumps(vectors, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(vectors, indent=1))
