"""Generates the rw01_f4_governed_real fixtures with the REAL Control Plane (#102 6648ae2c) and Registry (#86 52ff5f7d) sources. Not part of the Replay tests (needs PyNaCl).
Usage: RW01_SRC_DIR=<dir with control_plane/ registry/ replay/ symlinks> PYTHONPATH=<pynacl dir> python generate.py <outdir>"""
import sys, json, tempfile, os
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, "/dev/shm/f1q/qual/rw01_f4_poc/battery")
import harness as h
from tests.test_bounded_authorization import PROFILE
h.cp_bounded._now = lambda: h.NOW; h.cp_f4._now = lambda: h.NOW
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
def dump(sub, run_path, proposal):
    d = out / sub if sub else out; d.mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_bytes(Path(run_path).read_bytes())          # bytes exactly as written by CP BoundedRecordStore
    (d / "proposal.json").write_text(json.dumps(proposal, indent=1, sort_keys=True) + "\n")
tmp = Path(tempfile.mkdtemp(dir="/dev/shm"))
pr = h.produce(tmp, h.material(), carry=True, execute=True)
assert h.BoundedRecordStore(tmp / "run.json", "run-1").load().model_dump(mode="json") == json.loads((tmp / "run.json").read_text())
dump("", tmp / "run.json", pr.proposal)
t2 = Path(tempfile.mkdtemp(dir="/dev/shm"))
pr = h.produce(t2, h.material(), carry=True, execute=False)
p = h.tenant_proposal()
pr.flow.resolver.statuses[list(pr.flow.resolver.statuses)[0]].observed_at = (h.NOW - timedelta(seconds=500)).isoformat()
try: pr.flow.execute(p, pr.decision, adapter_id=p.adapter_id, now=h.NOW)
except Exception as e: print("execute refused (expected):", type(e).__name__)
assert json.loads((t2 / "run.json").read_text())["refusals"]
dump("effect_refusal", t2 / "run.json", json.loads(p.model_dump_json()))
t3 = Path(tempfile.mkdtemp(dir="/dev/shm"))
p = h.tenant_proposal()
rr = h.tenant_resolver_for(p)
rr.statuses[rr.contexts[PROFILE]["grant"]["grant_id"]].observed_at = (h.NOW - timedelta(seconds=30)).isoformat()
flow = h.build_flow(t3, h.material(10, 10), carry=True, resolver=rr)
d = flow.decide(p, now=h.NOW)
assert d.result == "hold", d.result
dump("hold_only", t3 / "run.json", json.loads(p.model_dump_json()))
