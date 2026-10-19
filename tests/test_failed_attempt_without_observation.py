"""A failed attempt that carries no observation is accepted, as the lifecycle contract allows.

The result status matrix and the null-observation rule already require a failed result to report ``observed_state``
'unknown'; every other attempted result without a validated observation must still be 'unknown'. Synthetic data only.
"""
from __future__ import annotations

import copy

import pytest

from . import test_contract_lifecycle_conformance as C
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow


def _unobserved_base():
    """The accepted null-observation import (an attempt whose observation is unavailable), as (cp, proposal, export)."""
    doc = copy.deepcopy(C.FIXTURES["result-failed-null-attempt-id"]["document"])
    C._name_attempt(doc)
    captured = {}
    original = C.run_import

    def capture(cp, proposal, executor=None):
        captured.update(cp=cp, proposal=proposal, export=executor)
        return C.Outcome(True, "captured")

    C.run_import = capture
    try:
        C.evaluate_doc(doc)
    finally:
        C.run_import = original
    return captured["cp"], captured["proposal"], captured["export"]


def _as_failed(export):
    """Result and owning rows of a failed attempt: terminal event and Control Plane row 'failed', no acknowledgement."""
    attempt = export["control_plane_attempts"][0]
    attempt.update(status="failed", error="x")
    attempt["acknowledgement"] = {"moltbot_safe_status": "failed", "attempt_id": export["execution_result"]["attempt_id"],
                                  "newly_executed": False}
    evidence = {"attempt": attempt, "reconciliation": export["control_plane_evidence"]["reconciliation"]}
    export["control_plane_evidence"] = evidence
    export["execution_result"]["control_plane_evidence"] = evidence
    return export


def _claim(export, status):
    """The same record claiming another terminal status (event, result flags and owning Control Plane row)."""
    export["execution_result"].update(status=status, acknowledged=True, newly_executed=False)
    export["attempt_events"][-1]["status"] = status
    attempt = export["control_plane_attempts"][0]
    attempt.update(status="partial" if status == "partial" else "acknowledged", error=None)
    attempt["acknowledgement"]["moltbot_safe_status"] = status
    export["control_plane_evidence"]["attempt"] = attempt
    export["execution_result"]["control_plane_evidence"] = export["control_plane_evidence"]


def _import(cp, proposal, export):
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=export, control_plane_revision=C.REVISION)


def _case():
    cp, proposal, export = _unobserved_base()
    return cp, proposal, _as_failed(export)


def test_a_failed_attempt_without_an_observation_imports():
    cp, proposal, export = _case()
    result = export["execution_result"]
    assert (result["status"], result["attempted"], result["observed_state"], result["observation"]) == (
        "failed", True, "unknown", None)
    assert _import(cp, proposal, export).status == "reconstruction_complete"


@pytest.mark.parametrize("status", ["executed", "reconciled", "partial"])
def test_other_attempted_results_without_an_observation_are_still_refused(status):
    cp, proposal, export = _case()
    _claim(export, status)
    with pytest.raises(ImportContractError):
        _import(cp, proposal, export)


@pytest.mark.parametrize("status", ["reconciled", "partial"])  # an executed result is refused earlier, by its own rule
def test_the_attempt_rule_itself_still_refuses_these_statuses(status, monkeypatch):
    """With the status matrix set aside, the attempt rule alone refuses them and still admits 'failed'."""
    from agent_replay_bundle import importers as I
    monkeypatch.setattr(I, "_result_matrix_problems", lambda result: [])
    cp, proposal, export = _case()
    _claim(export, status)
    with pytest.raises(ImportContractError) as info:
        _import(cp, proposal, export)
    assert "must remain unknown" in str(info.value), str(info.value)
    cp, proposal, export = _case()
    assert _import(cp, proposal, export).status == "reconstruction_complete"


@pytest.mark.parametrize("state", ["applied", "partial", "absent"])
def test_a_failed_attempt_with_an_observed_state_other_than_unknown_is_refused(state):
    cp, proposal, export = _case()
    export["execution_result"]["observed_state"] = state
    with pytest.raises(ImportContractError) as info:
        _import(cp, proposal, export)
    assert info.value.code == "null_observation_state_mismatch", str(info.value)


# ---- a failed result beside an accepted reconciliation observation --------------------------------------------

def _accepting_case():
    """The failed case whose reconciliation accepted an `absent` observation (a commit refused after the attempt)."""
    cp, proposal, export = _case()
    effect = export["execution_result"]["effect_id"]
    observation = {"effect_id": effect, "observed_at": "2026-10-05T19:00:00+00:00", "state": "absent",
                   "destination_state": {}}
    rec = copy.deepcopy(export["control_plane_evidence"]["reconciliation"])
    rec.update(result="observed_absent", observation=observation, observation_accepted=True, reasons=[])
    cp["reconciliations"][-1] = rec
    cp["observations"] = [r["observation"] for r in cp["reconciliations"] if r["observation_accepted"]]
    evidence = {"attempt": export["control_plane_evidence"]["attempt"], "reconciliation": rec}
    export["control_plane_evidence"] = evidence
    export["execution_result"]["control_plane_evidence"] = evidence
    return cp, proposal, export


def test_a_failed_attempt_without_an_observation_imports_beside_an_accepted_absent_reconciliation():
    cp, proposal, export = _accepting_case()
    assert export["execution_result"]["observation"] is None
    assert export["control_plane_evidence"]["reconciliation"]["observation_accepted"] is True
    assert _import(cp, proposal, export).status == "reconstruction_complete"


@pytest.mark.parametrize("status", ["reconciled", "partial", "unknown"])
def test_other_attempted_results_still_need_the_accepted_reconciliation_observation(status, monkeypatch):
    """With the status matrix set aside, a null observation beside an accepted reconciliation one is still refused."""
    from agent_replay_bundle import importers as I
    monkeypatch.setattr(I, "_result_matrix_problems", lambda result: [])
    cp, proposal, export = _accepting_case()
    _claim(export, status)
    if status == "unknown":
        export["execution_result"].update(acknowledged=False)
        export["control_plane_attempts"][0].update(status="unknown")
    with pytest.raises(ImportContractError) as info:
        _import(cp, proposal, export)
    # reconciled and partial are refused one rule earlier (they must remain unknown); unknown reaches this rule
    expected = ("accepted reconciliation observation missing" if status == "unknown" else "must remain unknown")
    assert expected in str(info.value), str(info.value)


def test_an_executed_attempt_beside_an_accepted_reconciliation_is_still_refused():
    cp, proposal, export = _accepting_case()
    _claim(export, "executed")
    with pytest.raises(ImportContractError):
        _import(cp, proposal, export)
