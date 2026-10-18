"""Capture real programme-2 N4 profile-on run records (merge-record/0.1, reversibility/0.1, dedupe-ttl/0.1, terminal-revocation/0.1) for the Replay fixtures.

Not a test and not vendored into the package. Run from a checkout of cogno-us/cognous-control-plane at 6093aca7
(`pip install -e .[dev]`), with this file outside the checkout:

    PYTHONPATH=src:. python capture_n4.py <out-dir>

It drives the Control Plane's own flows (helpers of tests/test_merge_record.py, tests/test_reversibility.py and tests/test_dedupe.py:
synthetic proposals, fixed clock, throwaway stores) and writes each run record unchanged. One file per scenario:
{"scenario", "profiles", "run"}.
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

import agent_control_plane.bounded as bounded
from tests.test_bounded_authorization import NOW

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
bounded._now = lambda: NOW

import tests.test_merge_record as tm
import tests.test_reversibility as tr
import tests.test_dedupe as td
import tests.test_terminal_revocation as tt
from tests.test_operation_identity import OPERATION, renew
from tests.test_bounded_authorization import ISSUER


def tmp():
    return Path(tempfile.mkdtemp(prefix="p4-"))


def save(name, f, profiles):
    run = json.loads(f.records.path.read_text(encoding="utf-8"))
    (OUT / f"{name}.json").write_text(json.dumps({"scenario": name, "profiles": profiles, "run": run}, indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print("captured", name, "members:", sorted(k for k in run if k in {"merge_records", "compensation_obligations", "snapshot_uses", "dedupe_escalations"}))


def ops():
    mp = pytest.MonkeyPatch()
    o = tm.Ops(tmp(), mp)
    o.adopt_rule()
    return o


def merge_before_second_effect():
    o = ops()
    o.decide(tm.A), o.decide(tm.B)
    o.execute(tm.A)
    o.merge()
    try:
        o.execute(tm.B)
    except PermissionError:
        pass
    save("merge-before-second-effect", o.f, ["operation-identity/0.1", "rule-revision/0.1", "merge-record/0.1"])


def merge_folded_dispatches_under_survivor():
    o = ops()
    o.decide(tm.A), o.decide(tm.B)
    o.merge()
    o.execute(tm.B)
    save("merge-folded-operation-dispatches-under-survivor", o.f, ["operation-identity/0.1", "rule-revision/0.1", "merge-record/0.1"])


def merge_after_both_applied():
    o = ops()
    o.decide(tm.A), o.decide(tm.B)
    o.execute(tm.A), o.execute(tm.B)
    o.merge()
    save("merge-after-both-applied-obligation", o.f, ["operation-identity/0.1", "rule-revision/0.1", "merge-record/0.1"])


def merge_held_and_unknown():
    o = ops()
    o.decide(tm.A), o.decide(tm.B)
    o.merge(by="urn:cognous:principal:nobody")
    o.merge(digest=tm.D2)
    o.execute(tm.A), o.execute(tm.B)
    save("merge-held-and-unknown-no-effect", o.f, ["operation-identity/0.1", "rule-revision/0.1", "merge-record/0.1"])


def reversibility_cached_accepted():
    p, r, f, cfg = tr.flow(tmp(), tr.cls("reversible_at_cost"))
    d = f.decide(p, now=NOW)
    tr.outage(r)
    tr.run(f, p, d, seconds=30)
    save("reversibility-cached-snapshot-accepted", f, ["reversibility/0.1"])


def reversibility_cached_refused():
    p, r, f, cfg = tr.flow(tmp(), tr.cls("reversible_at_cost"))
    d = f.decide(p, now=NOW)
    tr.outage(r)
    try:
        tr.run(f, p, d, seconds=61)
    except PermissionError:
        pass
    save("reversibility-cached-snapshot-stale-refused", f, ["reversibility/0.1"])


def reversibility_irreversible_refused():
    p, r, f, cfg = tr.flow(tmp(), tr.cls("irreversible"))
    d = f.decide(p, now=NOW)
    tr.outage(r)
    try:
        tr.run(f, p, d)
    except PermissionError:
        pass
    save("reversibility-irreversible-class-refused", f, ["reversibility/0.1"])


def terminal_revocation_recorded():
    p, r, f = tt.flow(tmp(), enabled=True)
    d = tt._refused_once_then_status_back(f, p, r, "revoked")
    try:
        f.execute(p, d, adapter_id=p.adapter_id, now=NOW)
    except PermissionError:
        pass
    f.decide(p, now=NOW)
    save("terminal-revocation-recorded-refused", f, ["terminal-revocation/0.1"])


def dedupe_escalation():
    mp = pytest.MonkeyPatch()
    p, r, f, c = td.flow(tmp(), mp, destination=lambda path: td.SilentDestination(path, capability=True))
    d = f.decide(p, now=NOW)
    td.go(f, p, d)
    # 301 s, not 300: the escalation deadline is inclusive since control plane 3cd17ead (ODES time semantics section 3), due only after it.
    f.escalation_pass(now=td.at(301))
    save("dedupe-unknown-attempt-escalated", f, ["operation-identity/0.1", "dedupe-ttl/0.1"])


def dedupe_in_progress():
    mp = pytest.MonkeyPatch()
    p, r, f, c = td.flow(tmp(), mp, destination=lambda path: td.SilentDestination(path, capability=True, mode="in_progress"))
    d1 = f.decide(p, now=NOW)
    td.go(f, p, d1)
    renew(r, f.runtime_authority_profile, "2")
    f.record_renewal(OPERATION, to_revision="2", written_by=ISSUER, now=NOW)
    d2 = f.decide(p, now=NOW)
    try:
        td.go(f, p, d2)
    except PermissionError:
        pass
    save("dedupe-in-progress-blocks-new-key", f, ["operation-identity/0.1", "dedupe-ttl/0.1"])


def dedupe_expired_key():
    mp = pytest.MonkeyPatch()
    f, p, d1, d2 = td._applied_then_expired_then_renewed(tmp(), mp, td.PROFILE)
    try:
        td.go(f, p, d2)
    except PermissionError:
        pass
    save("dedupe-expired-key-not-fresh", f, ["operation-identity/0.1", "dedupe-ttl/0.1"])


for fn in (terminal_revocation_recorded, merge_before_second_effect, merge_folded_dispatches_under_survivor, merge_after_both_applied, merge_held_and_unknown, reversibility_cached_accepted,
           reversibility_cached_refused, reversibility_irreversible_refused, dedupe_escalation, dedupe_in_progress, dedupe_expired_key):
    fn()
