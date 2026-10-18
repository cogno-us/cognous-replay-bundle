"""Capture real programme-2 profile-on run records for the Replay conformance fixtures.

Not a test and not vendored into the package. Run from a checkout of cogno-us/cognous-control-plane at 3755c71a
(`pip install -e .[dev]`), with this file outside the checkout:

    PYTHONPATH=src:. python capture_programme2.py <out-dir>

It drives the Control Plane's own flows (the helpers of tests/test_freshness.py, tests/test_operation_identity.py and
tests/test_rule_revision.py: synthetic proposals, a settable service clock, throwaway stores) with each opt-in profile on
(operation identity N1, rule revision N2, freshness N3) and writes each run record unchanged (ids are random uuids and
nonces; nothing is hand-edited). One file per scenario: {"scenario", "profiles", "run"}.
"""
import json
import sys
import tempfile
import threading
from datetime import timedelta
from pathlib import Path

import agent_control_plane.bounded as bounded
from agent_control_plane.bounded import CheckEvent, _process_owner, commitment
from agent_control_plane.freshness import AgeExtensionRefused
from agent_control_plane.operation_identity import OperationIdentityProfile
from tests.test_bounded_authorization import ISSUER, NOW, PROFILE
from tests.test_freshness import (Clock, authority, enable, execute, request, stale_grant, stall_before_dispatch,
                                  SIGNER, POLICY_SIGNER)
from tests.test_runtime_authority import bind_approval, setup_flow

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
CLOCK = Clock()
bounded._now = CLOCK
OPERATION = "op-order-100/refund-1"


def fresh():
    CLOCK.now = NOW
    return Path(tempfile.mkdtemp(prefix="p3-"))


def save(name, f, profiles):
    run = json.loads(f.records.path.read_text(encoding="utf-8"))
    (OUT / f"{name}.json").write_text(json.dumps({"scenario": name, "profiles": profiles, "run": run}, indent=1, ensure_ascii=False) + "\n",
                                      encoding="utf-8")
    print("captured", name, "members:", sorted(k for k in run if k not in {"run_id", "decisions", "attempts", "observations",
                                                                              "reconciliations", "refusals", "resolution_checks",
                                                                              "closeouts", "check_events", "input_time_floors"}))


def flow(*, freshness=False, identity=False, rules=False, **options):
    p, r, f, c = setup_flow(fresh())
    if freshness:
        c = enable(r, f, c, **options)
    if identity:
        c = c.model_copy(update={"operation_identity": OperationIdentityProfile(resolver_id="synthetic-resolver", resolver_version="1")})
        r.contexts[PROFILE]["runtime_authority"]["operation_id"] = OPERATION
        bind_approval(r, c)
        f.runtime_authority_profile = c.snapshot()
    if rules:
        authority(f, r)
    return p, r, f, c


def attempt(f, p, d):
    try:
        return execute(f, p, d)
    except PermissionError:
        return None


def default_path():
    p, r, f, c = setup_flow(fresh())
    d = f.decide(p, now=NOW)
    execute(f, p, d)
    save("default-path", f, [])


def identity_applied_renewed():
    p, r, f, c = flow(identity=True)
    d = f.decide(p, now=NOW)
    execute(f, p, d)
    f.record_renewal(OPERATION, to_revision="2", written_by=ISSUER, now=NOW)
    try:
        f.record_renewal(OPERATION, to_revision="2", written_by=p.actor, now=NOW)
    except PermissionError:
        pass
    save("identity-applied-renewed", f, ["operation-identity/0.1"])


def identity_lost_ack_reconciled():
    p, r, f, c = flow(identity=True)
    d = f.decide(p, now=NOW)
    f.execute(p, d, adapter_id=p.adapter_id, now=NOW, lose_ack=True)
    f.reconcile(d.effect_id, now=NOW)
    f.execute(p, d, adapter_id=p.adapter_id, now=NOW)
    save("identity-lost-ack-reconciled", f, ["operation-identity/0.1"])


def identity_effect_time_refusal():
    p, r, f, c = flow(identity=True)
    d = f.decide(p, now=NOW)
    next(iter(r.statuses.values())).status = "revoked"
    attempt(f, p, d)
    save("identity-effect-time-refusal", f, ["operation-identity/0.1"])


def rules_adopted():
    p, r, f, c = flow(rules=True)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    execute(f, p, d)
    save("rules-adopted-applied", f, ["rule-revision/0.1"])


def rules_refused_revision():
    p, r, f, c = flow(rules=True)
    from agent_control_plane.rule_revision import RuleRevision, append_rule_revision
    from tests.test_freshness import OTHER, POLICY_REF
    try:
        append_rule_revision(f.records, f.rule_revision_profile, RuleRevision(
            revision_id="self-signed-1", rule_kind="policy", rule_ref=POLICY_REF, from_digest=None, to_digest="sha256:" + "ab" * 32,
            reviser=OTHER, signer=OTHER, authority_ref="synthetic-authority:2", reason="synthetic", recorded_at=NOW.isoformat()))
    except Exception:
        pass
    d = f.decide(p, now=NOW)
    attempt(f, p, d)
    save("rules-self-signed-revision-refused", f, ["rule-revision/0.1"])


def freshness_applied():
    p, r, f, c = flow(freshness=True)
    CLOCK.tick(2)
    d = f.decide(p, now=NOW)
    CLOCK.tick(3)
    execute(f, p, d)
    save("freshness-applied", f, ["freshness/0.1"])


def freshness_slow_reads():
    p, r, f, c = flow(freshness=True)
    original = r.identity_status

    def slow(*a):
        CLOCK.tick(7)
        return original(*a)
    r.identity_status = slow
    d = f.decide(p, now=NOW)
    CLOCK.tick(3)
    execute(f, p, d)
    save("freshness-slow-reads-applied", f, ["freshness/0.1"])


def freshness_expired():
    p, r, f, c = flow(freshness=True)
    d = f.decide(p, now=NOW)
    stall_before_dispatch(f, CLOCK, 61, pin_observation=True)
    attempt(f, p, d)
    save("freshness-expired-before-dispatch", f, ["freshness/0.1"])


def freshness_expired_observation_after_pass():
    p, r, f, c = flow(freshness=True)
    d = f.decide(p, now=NOW)
    stall_before_dispatch(f, CLOCK, 61)
    attempt(f, p, d)
    save("freshness-expired-observation-after-pass", f, ["freshness/0.1"])


def freshness_overdue():
    p, r, f, c = flow(freshness=True)
    release, started = threading.Event(), threading.Event()
    original = r.grant_status

    def blocked(ref):
        started.set()
        release.wait(20)
        return original(ref)
    r.grant_status = blocked
    thread = threading.Thread(target=lambda: f.decide(p, now=NOW))
    thread.start()
    assert started.wait(10)
    CLOCK.tick(61)
    f.records.recovery_pass(trigger="manual", record_run=True)
    release.set()
    thread.join(20)
    save("freshness-overdue-recovery-run", f, ["freshness/0.1"])


def freshness_reaper():
    p, r, f, c = flow(freshness=True, reaper_interval_seconds=30)
    f.records.append_check_event(CheckEvent(check_id="orphan", phase="opened", stage="decision", recorded_at=NOW.isoformat(),
                                            owner=_process_owner(), proposal_commitment=commitment({}),
                                            deadline=(NOW + timedelta(seconds=60)).isoformat(), age_bound_seconds=60))
    reaper = f.reaper(clock=CLOCK)
    reaper.run_due()
    CLOCK.tick(35)
    reaper.run_due()
    save("freshness-reaper-recovery-runs", f, ["freshness/0.1"])


def freshness_live_overdue_check():
    """A decision is complete; a second check is still open (its read is blocked) and past its deadline when the recovery pass
    runs: the record is saved while the check is live, so it carries an open overdue check, an overdue event and a run row."""
    p, r, f, c = flow(freshness=True)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    release, started = threading.Event(), threading.Event()
    original = r.grant_status

    def blocked(ref):
        started.set()
        release.wait(20)
        return original(ref)
    r.grant_status = blocked
    thread = threading.Thread(target=lambda: f.decide(p, now=NOW))
    thread.start()
    assert started.wait(10)
    CLOCK.tick(61)
    f.records.recovery_pass(trigger="manual", record_run=True)
    save("freshness-live-overdue-check", f, ["freshness/0.1"])
    release.set()
    thread.join(20)


def freshness_reaper_after_decision():
    """The reaper closes an orphaned opening (interrupted) and later reports a live late one (overdue), next to a real decision."""
    p, r, f, c = flow(freshness=True, reaper_interval_seconds=30)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    f.records.append_check_event(CheckEvent(check_id="orphan", phase="opened", stage="decision", recorded_at=NOW.isoformat(),
                                            owner=_process_owner(), proposal_commitment=commitment({}),
                                            deadline=(NOW + timedelta(seconds=60)).isoformat(), age_bound_seconds=60))
    reaper = f.reaper(clock=CLOCK)
    reaper.run_due()
    CLOCK.tick(35)
    reaper.run_due()
    save("freshness-reaper-after-decision", f, ["freshness/0.1"])


def freshness_extension():
    p, r, f, c = flow(freshness=True, max_age_extension_seconds=300)
    authority(f, r)
    stale_grant(r, 70)
    assert f.decide(p, now=NOW).result == "hold"
    for override in ({"signer": None}, {"signer": "urn:cognous:principal:nobody"}):
        try:
            request(f, **override)
        except AgeExtensionRefused:
            pass
    request(f)
    ok = f.decide(p, now=NOW)
    assert ok.result == "authorized", ok.reasons
    save("freshness-extension-accepted-and-refused", f, ["freshness/0.1", "rule-revision/0.1"])


def freshness_nonce():
    p, r, f, c = flow(freshness=True)
    r.echo_nonce = True
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    execute(f, p, d)
    save("freshness-nonce-bound", f, ["freshness/0.1"])


def freshness_nonce_replay():
    p, r, f, c = flow(freshness=True)
    r.echo_nonce = True
    d = f.decide(p, now=NOW)
    recorded = {}
    original = r.nonce_read

    def recording(nonce, method, *args):
        recorded[method] = original(nonce, method, *args)
        return recorded[method]
    r.nonce_read = recording
    f.decide(p, now=NOW)

    def replaying(nonce, method, *args):
        if method == "grant_status":
            return recorded["grant_status"][0], recorded["grant_status"][1]
        return original(nonce, method, *args)
    r.nonce_read = replaying
    attempt(f, p, d)
    save("freshness-nonce-replay-refused", f, ["freshness/0.1"])


def all_three_applied():
    p, r, f, c = flow(freshness=True, identity=True, rules=True)
    CLOCK.tick(2)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    CLOCK.tick(3)
    execute(f, p, d)
    f.record_renewal(OPERATION, to_revision="2", written_by=ISSUER, now=NOW)
    save("all-three-applied-renewed", f, ["operation-identity/0.1", "rule-revision/0.1", "freshness/0.1"])


def all_three_expired():
    p, r, f, c = flow(freshness=True, identity=True, rules=True)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    stall_before_dispatch(f, CLOCK, 61, pin_observation=True)
    attempt(f, p, d)
    f.records.recovery_pass(trigger="manual", record_run=True)
    save("all-three-expired-before-dispatch", f, ["operation-identity/0.1", "rule-revision/0.1", "freshness/0.1"])


def all_three_lost_ack():
    p, r, f, c = flow(freshness=True, identity=True, rules=True)
    d = f.decide(p, now=NOW)
    f.execute(p, d, adapter_id=p.adapter_id, now=NOW, lose_ack=True)
    f.reconcile(d.effect_id, now=NOW)
    save("all-three-lost-ack-reconciled", f, ["operation-identity/0.1", "rule-revision/0.1", "freshness/0.1"])


for fn in (default_path, identity_applied_renewed, identity_lost_ack_reconciled, identity_effect_time_refusal, rules_adopted,
           rules_refused_revision, freshness_applied, freshness_slow_reads, freshness_expired, freshness_expired_observation_after_pass,
           freshness_overdue, freshness_reaper, freshness_live_overdue_check, freshness_reaper_after_decision, freshness_extension, freshness_nonce, freshness_nonce_replay, all_three_applied,
           all_three_expired, all_three_lost_ack):
    fn()
