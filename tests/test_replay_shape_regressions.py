"""Regressions for legitimate real-producer shapes that Replay must accept, and the defects it must still reject.

Shapes come from the runtime route-C executor (observation unavailable after an acknowledged delivery), the Control
Plane reconciliation path (``bounded.py`` mints a single ``reconciled_existing`` attempt record) and concurrent
resolution checks. Each positive case is paired with negatives showing the neighbouring genuine defect is still
rejected. Synthetic data only; planted in deep copies of tests/fixtures/security_runtime_valid/.
"""
from __future__ import annotations

import copy

import pytest

from agent_replay_bundle.importers import ImportContractError

from .test_audit_defect_detection import load, rejects, run

UNAVAILABLE = "observation_unavailable:ConnectionError"


def _unresolved_delivery(cp, x):
    """Acknowledged delivery whose Control Plane observation is unavailable: result 'unknown', terminal 'executed'."""
    result = x["execution_result"]
    result.update(status="unknown", observation=None, observed_state="unknown", error=UNAVAILABLE)
    reconciliation = result["control_plane_evidence"]["reconciliation"]
    reconciliation.update(result="hold", observation=None, observation_accepted=False, reasons=[UNAVAILABLE])
    x["control_plane_evidence"] = result["control_plane_evidence"]
    x["observations"] = []
    cp["reconciliations"] = [copy.deepcopy(reconciliation)]
    cp["observations"] = []


def _accepts(mutate):
    cp, proposal, executor = load()
    mutate(cp, executor)
    return run(cp, proposal, executor)


# ---- result 'unknown' with terminal 'executed' ------------------------------------------------

def test_unknown_result_with_executed_terminal_is_accepted_when_observation_is_unavailable():
    assert _accepts(_unresolved_delivery).status == "reconstruction_complete"


@pytest.mark.parametrize("name,mutate,match", [
    ("observed_state_not_unknown", lambda cp, x: x["execution_result"].__setitem__("observed_state", "applied"),
     "null observation cannot establish observed state|contradicts the terminal attempt event"),
    ("terminal_not_executed", lambda cp, x: x["attempt_events"][-1].__setitem__("status", "failed"),
     "contradicts the terminal attempt event"),
    ("terminal_dropped", lambda cp, x: x["attempt_events"].pop(-1), "contradicts the terminal attempt event"),
    ("observation_present", lambda cp, x: x["execution_result"].__setitem__("observation", {"state": "applied"}),
     "contradicts the terminal attempt event|observation"),
])
def test_unknown_result_shape_still_rejects_genuine_defects(name, mutate, match):
    def plant(cp, x):
        _unresolved_delivery(cp, x)
        mutate(cp, x)
    rejects(plant, match)


# ---- reconciled-existing attempt lifecycle ----------------------------------------------------

def _reconciled_attempt(acknowledgement):
    def plant(cp, x):
        row = dict(copy.deepcopy(cp["attempts"][-1]), attempt_id="cp-reconciled-1", status="acknowledged",
                   acknowledgement=acknowledgement)
        cp["attempts"].append(row)
    return plant


def test_single_reconciled_existing_attempt_needs_no_start_record():
    assert _accepts(_reconciled_attempt({"reconciled_existing": True})).status == "reconstruction_complete"


@pytest.mark.parametrize("acknowledgement", [{}, {"reconciled_existing": False}, {"reconciled_existing": True, "x": 1}])
def test_single_attempt_without_reconciled_marker_still_requires_start_record(acknowledgement):
    rejects(_reconciled_attempt(acknowledgement), "lacks its attempted start record")


def test_dropped_start_record_is_still_rejected():
    rejects(lambda cp, x: cp["attempts"].pop(0), "lacks its attempted start record")


# ---- resolution check ordering ----------------------------------------------------------------

def _overlap_checks(cp, x):
    """Run the effect check entirely inside the decision check, so the two checks are concurrent."""
    events = cp["check_events"]
    decision_id = events[0]["check_id"]
    decision = [e for e in events if e["check_id"] == decision_id]
    effect = [e for e in events if e["check_id"] != decision_id]
    cp["check_events"] = decision[:1] + effect + decision[1:]


def test_overlapping_checks_may_complete_out_of_resolution_check_order():
    # Journal completion order is effect then decision; resolution_checks hold decision then effect.
    assert _accepts(_overlap_checks).status == "reconstruction_complete"


def test_overlapping_checks_may_complete_in_resolution_check_order():
    assert _accepts(lambda cp, x: (_overlap_checks(cp, x), cp["resolution_checks"].reverse())).status == "reconstruction_complete"


@pytest.mark.parametrize("reorder", [lambda r: r.reverse(), lambda r: r.insert(0, r.pop(1))])
def test_sequential_checks_reordered_are_still_rejected(reorder):
    rejects(lambda cp, x: reorder(cp["resolution_checks"]), "out of journal order")
