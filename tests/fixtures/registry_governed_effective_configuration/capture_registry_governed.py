"""Capture REAL Registry-governed Control Plane run records (Registry r08-v8 a40fe755 + Control Plane b19c47dd).

Not a test; not vendored in the package. Run from a pristine Control Plane checkout at b19c47ddd020409d24e52e70b11359c46265edbb with a Registry checkout at
a40fe755e2384a99c37016fa9ad59396f1835900 and PyNaCl importable:

    PYTHONPATH=<site-with-pynacl>:src:. OCS_REGISTRY_PIN_DIR=<registry checkout> OCS_REQUIRE_REGISTRY_PIN=1 python capture_registry_governed.py <out-dir>

Drives the Control Plane's own tests/final3_support.py builders (the repository's own Registry-governed workflow; synthetic Ed25519 material; synthetic clock). Writes
control_plane_run.json and proposal.json per scenario exactly as the Control Plane's BoundedRecordStore persisted them. Nothing is edited after capture.
"""
import json, sys, tempfile
from pathlib import Path
import pytest
from tests.final3_support import *   # noqa: F401,F403  (enforces the exact r08-v8 Registry pin and PyNaCl)
import tests.final3_support as F
from tests import d06_support as D

OUT = Path(sys.argv[1])
mp = pytest.MonkeyPatch(); D.patch_clock(mp)
BASE = {"anc": "anchor", "age": 60, "tol": 2}

def stage(conf, store=None, tp=None):
    tp = tp or Path(tempfile.mkdtemp(prefix="reggov-"))
    p, res, cfg = base.prepared(tp / "w", t1=R_, freshness=FreshnessProfile(anchor_deadline_to_inputs=False))
    store = store or (tp / "store"); store.mkdir(exist_ok=True)
    flow = F.make(store, res, cfg, conf)
    bind_approval(res, flow.runtime_authority_profile)
    return p, res, cfg, store, flow, tp

def dump(name, store, p):
    d = OUT / name; d.mkdir(parents=True, exist_ok=True)
    rec = json.loads((store / "run.json").read_text())
    (d / "control_plane_run.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    (d / "proposal.json").write_text(json.dumps(p.model_dump(mode="json"), indent=1, sort_keys=True, default=str) + "\n")
    print(name, [x["result"] for x in rec["decisions"]], len(rec["attempts"]), len(rec["refusals"]))

# 1. authorized + executed under configuration A
p, res, cfg, store, flow, tp = stage(BASE)
d = flow.decide(p, now=NOW); assert d.result == "authorized"
flow.execute(p, flow.records.decision(d.decision_id), adapter_id=p.adapter_id, now=NOW)
dump("governed_executed", store, p)

# 2. authorized under A, rebuilt under B (age 61), execute refused authorization_binding_changed
p, res, cfg, store, flow, tp = stage(BASE)
d = flow.decide(p, now=NOW)
wf = F.make(store, res, cfg, dict(BASE, age=61)); bind_approval(res, wf.runtime_authority_profile)
try:
    wf.execute(p, wf.records.decision(d.decision_id), adapter_id=p.adapter_id, now=NOW)
except Exception as e:
    print("expected refusal:", type(e).__name__, e)
dump("governed_binding_changed", store, p)

# 3. authorized under A (not executed)
p, res, cfg, store, flow, tp = stage(BASE)
d = flow.decide(p, now=NOW)
dump("governed_decided_only", store, p)

# 4. one declared family only (observation_max_age), host observation policy kept
p, res, cfg, store, flow, tp = stage({"age": 60})
d = flow.decide(p, now=NOW); assert d.result == "authorized", d.reasons
flow.execute(p, flow.records.decision(d.decision_id), adapter_id=p.adapter_id, now=NOW)
dump("governed_age_only", store, p)

