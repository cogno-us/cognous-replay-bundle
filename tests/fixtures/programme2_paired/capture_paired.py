"""Capture executor-paired runs: Control Plane 3cd17ead run record + proposal + runtime 11de097c export, per scenario.

Not a test and not vendored into the package. Run with a Control Plane checkout at 3cd17ead and a runtime checkout at 11de097c on
the path (both installed or on PYTHONPATH), from the control plane checkout:

    PYTHONPATH=src:.:<runtime checkout> python capture_paired.py <out-dir> <runtime-revision>

Drives the Control Plane's own flow helpers (tests/test_runtime_authority.py setup_flow, tests/test_operation_identity.py enable) with the
runtime's PinnedControlPlaneExecutor (adapter route) and AtomicLocalControlPlaneExecutor (atomic claim route), writes
control_plane_run.json / proposal.json / executor.json per scenario unchanged (synthetic data, throwaway stores).
"""
import json
import sys
import tempfile
from pathlib import Path

import pytest

import agent_control_plane.bounded as bounded
from agent_control_plane.bounded import commitment
from tests.test_bounded_authorization import NOW, PROFILE, INSTITUTION
from tests.test_runtime_authority import bind_approval, setup_flow
from tests.test_operation_identity import enable
from engine.effective_grant import EffectiveGrantDestination, DERIVATION
from engine.operation_identity_destination import OperationIdentityEffectiveGrantDestination
from engine.operation_identity_atomic_destination import OperationIdentityAtomicAuthorityEffectDestination
from engine.local_authority_effect import AtomicAuthorityEffectDestination
from engine.safe_executor import ExecutionOperation, ExecutionEnvelope, EXECUTION_ENVELOPE_VERSION, LocalExecutionPolicy
from engine.control_plane_adapter import PinnedControlPlaneExecutor
from engine.atomic_local_control_plane_executor import AtomicLocalControlPlaneExecutor
from engine.producer_contract import export_execution_artifacts

OUT = Path(sys.argv[1])
REVISION = sys.argv[2]
bounded._now = lambda: NOW


def tmp():
    return Path(tempfile.mkdtemp(prefix="p4pair-"))


def envelope_and_policy(p, d):
    fields = {k: getattr(p, k) for k in ["actor", "principal", "manifest_id", "manifest_version", "manifest_digest", "action_id", "adapter_id",
                                         "target", "payload", "payload_commitment", "amount", "unit", "effects", "requirement_id"]}
    op = ExecutionOperation(**fields, institution_id=INSTITUTION, authority_domain="customer-refunds",
                            proposal_commitment=commitment(p.model_dump(mode="json")), requested_permissions=tuple(p.requested_permissions),
                            authority_context_id=p.authority_context_ref, grant_id=d.binding.grant_id,
                            grant_revision=d.binding.grant_revision, effective_max_effects=d.binding.effective_max_effects)
    pol = LocalExecutionPolicy(allowed_institutions=frozenset({INSTITUTION}), allowed_authority_domains=frozenset({"customer-refunds"}),
                               allowed_adapters=frozenset({p.adapter_id}), allowed_actions=frozenset({p.action_id}),
                               allowed_target_prefixes=("urn:cognous:synthetic-account:",), allowed_units=frozenset({"USD"}),
                               max_amount=1000, max_effects=1)
    return ExecutionEnvelope(EXECUTION_ENVELOPE_VERSION, d.decision_id, d.effect_id, op), pol


def save(name, f, p, export, profiles, run=None):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    run = run if run is not None else f.records.load().model_dump(mode="json")
    (d / "control_plane_run.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    (d / "proposal.json").write_text(json.dumps(p.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    (d / "executor.json").write_text(json.dumps(export, indent=2, sort_keys=True, default=str) + "\n")
    print("captured", name)


def adapter_flow(identity):
    p, r, f, c = setup_flow(tmp() / "cp")
    cls = EffectiveGrantDestination
    if identity:
        c = enable(r, f, c)
        cls = OperationIdentityEffectiveGrantDestination
    grant = r.contexts[PROFILE]["grant"]
    dest = cls(tmp() / "sqlite")
    digest = dest.set_effective_grant(principal=p.principal, grant_id=grant["grant_id"], revision=grant["revision"], permissions=p.requested_permissions)
    r.contexts[PROFILE]["runtime_authority"].update(expected_effective_grant_digest=digest, effective_grant_derivation_version=DERIVATION)
    bind_approval(r, c)
    f.runtime_authority_profile = c.snapshot() if identity else f.runtime_authority_profile
    f.destination = dest
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    env, pol = envelope_and_policy(p, d)
    ex = PinnedControlPlaneExecutor(workflow=f, destination=dest, policy=pol, observation_clock=lambda: NOW)
    result = ex.execute(envelope=env, proposal=p, decision=d, now=NOW)
    export = export_execution_artifacts(env, result, dest, repository_revision=REVISION)
    return p, f, result, export, None


def atomic_flow(identity):
    p, r, f, c = setup_flow(tmp() / "cp")
    if identity:
        c = enable(r, f, c)
    grant = r.contexts[PROFILE]["grant"]
    dest_cls = OperationIdentityAtomicAuthorityEffectDestination if identity else AtomicAuthorityEffectDestination
    dest = dest_cls(tmp() / "sqlite", clock=lambda: NOW)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    env, pol = envelope_and_policy(p, d)
    ex = AtomicLocalControlPlaneExecutor(workflow=f, destination=dest, policy=pol, operation_identity=identity)
    # The record is taken before claim issuance: the Control Plane's own claim issuance journals a decision-stage check next to
    # a claim-stage resolution check, which Replay refuses at every generation (finding, see the PR); the claim is still the
    # Control Plane's own, only its record is left out.
    before_claim = f.records.load().model_dump(mode="json")
    claim = ex.provision_claim(proposal=p, decision=d, now=NOW, claim_id="claim-1")
    result = ex.execute(envelope=env, claim_id="claim-1")
    export = export_execution_artifacts(env, result, dest, repository_revision=REVISION)
    tables = {r[0] for r in dest._connect().execute("SELECT name FROM sqlite_master")}
    keyed = dest._connect().execute("SELECT COUNT(*) FROM operation_effects_v1").fetchone()[0] if "operation_effects_v1" in tables else None
    print("operation key rows at the destination:", keyed)
    assert (keyed == 1) if identity else (keyed is None)
    return p, f, result, export, before_claim


for name, fn, identity, profiles in (("adapter-default", adapter_flow, False, []), ("adapter-operation-identity", adapter_flow, True, ["operation-identity/0.1"]),
                                     ("atomic-default", atomic_flow, False, []), ("atomic-operation-key", atomic_flow, True, ["operation-identity/0.1"])):
    try:
        p, f, result, export, run = fn(identity)
        print(name, result.status, result.attempted, result.error)
        save(name, f, p, export, profiles, run)
    except Exception:
        import traceback
        traceback.print_exc()
        print("FAILED", name)
