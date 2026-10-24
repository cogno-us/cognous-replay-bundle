"""Capture route B revocation scenarios: Control Plane run record + proposal + runtime export (+ behaviour.json) per scenario.

Not a test and not vendored into the package. From a Control Plane checkout at 7a4bcd40 with a runtime checkout on the path:

    PYTHONPATH=src:.:<runtime checkout> python capture_revocation.py <out-dir> <runtime-revision> [amount]

Drives the Control Plane's own flow helpers through AtomicLocalControlPlaneExecutor (operation identity on): revoke the grant
(denied-grant-revoked, fixture denied/), revoke the approval (denied-approval-revoked, fixture denied_approval_revoked/), revoke then
re-activate the approval (approval-revoked-then-reactivated: executed before runtime F3, the re-activation is refused and the
execution denied from c5e97e87), and a control without revocation. The fixtures were captured with amount 10.0. Synthetic data,
throwaway stores, nothing hand-edited.
"""
"""Capture executor-paired runs: Control Plane run record + proposal + runtime export, per scenario.

Not a test and not vendored into the package. Run with a Control Plane checkout at 6093aca7 and a runtime checkout at 62a5cc15 on
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

import tests.test_runtime_authority as _tra
AMOUNT = float(sys.argv[3]) if len(sys.argv) > 3 else None
if AMOUNT is not None:
    _orig_proposal = _tra.proposal
    _tra.proposal = lambda *a, **k: _orig_proposal(*a, **k).model_copy(update={"amount": AMOUNT})
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




def build():
    p, r, f, c = setup_flow(tmp() / "cp")
    c = enable(r, f, c)
    dest = OperationIdentityAtomicAuthorityEffectDestination(tmp() / "sqlite", clock=lambda: NOW)
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    env, pol = envelope_and_policy(p, d)
    ex = AtomicLocalControlPlaneExecutor(workflow=f, destination=dest, policy=pol, operation_identity=True)
    ex.provision_claim(proposal=p, decision=d, now=NOW, claim_id="claim-1")
    return p, f, d, env, dest, ex


def approval_refs(dest):
    return [row[0] for row in dest._connect().execute("SELECT approval_ref FROM authority_approvals_v1")]


def save(name, p, f, export, behaviour):
    out = OUT / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "control_plane_run.json").write_text(json.dumps(f.records.load().model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    (out / "proposal.json").write_text(json.dumps(p.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    (out / "executor.json").write_text(json.dumps(export, indent=2, sort_keys=True, default=str) + "\n")
    (out / "behaviour.json").write_text(json.dumps(behaviour, indent=2, sort_keys=True, default=str) + "\n")
    print("captured", name, behaviour)


def run(name, steps):
    p, f, d, env, dest, ex = build()
    behaviour = {"approval_refs": len(approval_refs(dest))}
    for i, (label, fn) in enumerate(steps):
        try:
            behaviour[label] = fn(dest, d, ex, env)
        except Exception as exc:  # recorded, not hidden
            behaviour[label] = "raised " + type(exc).__name__ + ": " + str(exc)
    result = ex.execute(envelope=env, claim_id="claim-1")
    behaviour["final_execute"] = {"status": result.status, "attempted": result.attempted, "error": result.error,
                                  "evidence": dict(result.control_plane_evidence or {}) and {k: v for k, v in result.control_plane_evidence.items() if k != "failure_record_id"}}
    export = export_execution_artifacts(env, result, dest, repository_revision=REVISION)
    save(name, p, f, export, behaviour)


def revoke_grant(dest, d, ex, env):
    dest.set_grant_status(d.binding.grant_id, status="revoked")
    return "ok"


def revoke_approval(dest, d, ex, env):
    for ref in approval_refs(dest):
        dest.set_approval_status(ref, status="revoked")
    return "ok"


def reactivate_approval(dest, d, ex, env):
    for ref in approval_refs(dest):
        dest.set_approval_status(ref, status="active")
    return "ok"


run("denied-grant-revoked", [("revoke_grant", revoke_grant)])
run("denied-approval-revoked", [("revoke_approval", revoke_approval)])
run("approval-revoked-then-reactivated", [("revoke_approval", revoke_approval), ("reactivate_approval", reactivate_approval)])
run("control-no-revocation", [])
