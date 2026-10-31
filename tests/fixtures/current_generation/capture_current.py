"""Capture the nine plain current-generation scenarios: Control Plane run record + proposal + Runtime export.

Not a test and not vendored into the package. Run from a pristine Control Plane checkout at
b19c47ddd020409d24e52e70b11359c46265edbb with a pristine Runtime checkout at f7a55e2a8494801e49193f9f46935f0a971c248d on the path:

    PYTHONPATH=src:.:<runtime checkout> python capture_current.py <out-dir>

Drives the Control Plane's own flow helper (tests/test_runtime_authority.py setup_flow, bind_approval) with the Runtime's
PinnedControlPlaneExecutor, then export_execution_artifacts(repository_revision=<runtime revision>). Writes
control_plane_run.json / proposal.json / runtime_export.json per scenario unchanged (synthetic data, throwaway stores).
"""
import json
import sys
import tempfile
from pathlib import Path

import agent_control_plane.bounded as bounded
from agent_control_plane.bounded import commitment
from tests.test_runtime_authority import INSTITUTION, NOW, PROFILE, bind_approval, setup_flow
from engine.effective_grant import DERIVATION, EffectiveGrantDestination
from engine.safe_executor import EXECUTION_ENVELOPE_VERSION, ExecutionEnvelope, ExecutionOperation, LocalExecutionPolicy
from engine.control_plane_adapter import PinnedControlPlaneExecutor
from engine.producer_contract import export_execution_artifacts

RUNTIME_REVISION = "f7a55e2a8494801e49193f9f46935f0a971c248d"
CASES = ["valid", "lost_ack", "revoked", "unreadable", "purpose_closed", "purpose_reopened", "tampered_evidence", "input_dropped", "race"]
OUT = Path(sys.argv[1])
bounded._now = lambda: NOW


def capture(case):
    tmp = Path(tempfile.mkdtemp(prefix="curgen-"))
    p, r, f, c = setup_flow(tmp / "cp", purpose=case.startswith("purpose"))
    grant = r.contexts[PROFILE]["grant"]
    dest = EffectiveGrantDestination(tmp / "sqlite")
    digest = dest.set_effective_grant(principal=p.principal, grant_id=grant["grant_id"], revision=grant["revision"], permissions=p.requested_permissions)
    r.contexts[PROFILE]["runtime_authority"].update(expected_effective_grant_digest=digest, effective_grant_derivation_version=DERIVATION)
    bind_approval(r, c)
    f.destination = dest
    d = f.decide(p, now=NOW)
    assert d.result == "authorized", d.reasons
    fields = {k: getattr(p, k) for k in ["actor", "principal", "manifest_id", "manifest_version", "manifest_digest", "action_id", "adapter_id",
                                         "target", "payload", "payload_commitment", "amount", "unit", "effects", "requirement_id"]}
    op = ExecutionOperation(**fields, institution_id=INSTITUTION, authority_domain="customer-refunds",
                            proposal_commitment=commitment(p.model_dump(mode="json")), requested_permissions=tuple(p.requested_permissions),
                            authority_context_id=p.authority_context_ref, grant_id=d.binding.grant_id, grant_revision=d.binding.grant_revision,
                            effective_max_effects=d.binding.effective_max_effects)
    pol = LocalExecutionPolicy(allowed_institutions=frozenset({INSTITUTION}), allowed_authority_domains=frozenset({"customer-refunds"}),
                               allowed_adapters=frozenset({p.adapter_id}), allowed_actions=frozenset({p.action_id}),
                               allowed_target_prefixes=("urn:cognous:synthetic-account:",), allowed_units=frozenset({"USD"}), max_amount=1000, max_effects=1)
    ex = PinnedControlPlaneExecutor(workflow=f, destination=dest, policy=pol, observation_clock=lambda: NOW)
    env = ExecutionEnvelope(EXECUTION_ENVELOPE_VERSION, d.decision_id, d.effect_id, op)
    if case == "unreadable":
        def broken(ref):
            raise TimeoutError()
        r.grant_status = broken
    elif case == "revoked":
        next(iter(r.statuses.values())).status = "revoked"
    elif case == "purpose_closed":
        r.purpose.state = "closed"
    elif case == "purpose_reopened":
        r.purpose.epoch = "new-epoch"
    elif case == "tampered_evidence":
        next(iter(r.evidence.values())).validation_record["statement"]["values"]["validated_count"] = 999
    elif case == "input_dropped":
        r.contexts[PROFILE]["requirement"]["evidence"] = []
    elif case == "race":
        original = dest.commit

        def race(snapshot, **kwargs):
            dest.set_effective_grant(principal=p.principal, grant_id=d.binding.grant_id, revision="2", permissions=p.requested_permissions + ["admin"])
            return original(snapshot, **kwargs)
        dest.commit = race
    res = ex.execute(envelope=env, proposal=p, decision=d, now=NOW, simulate="lost_ack" if case == "lost_ack" else None)
    export = export_execution_artifacts(env, res, dest, repository_revision=RUNTIME_REVISION)
    out = OUT / case
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in (("control_plane_run.json", f.records.load().model_dump(mode="json")), ("proposal.json", p.model_dump(mode="json")), ("runtime_export.json", export)):
        (out / name).write_text(json.dumps(payload, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(case, res.status)


for case in CASES:
    capture(case)
