"""Regression tests: planted audit/export defects in producer artifacts must be rejected, clean exports accepted.

Derived from the cognous-stack-qualification SCN-D08 / SCN-C23 misses (failure register F-06, F-12). Defects are
planted in deep copies of the real-producer fixture in tests/fixtures/security_runtime_valid/ (synthetic data only).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow
from agent_replay_bundle.refusal_evidence import validate_run

FIXTURE = Path(__file__).parent / "fixtures" / "security_runtime_valid"
REVISION = I.CONTROL_PLANE_F5B_REVISION
EXECUTOR_REVISION = I.MOLTBOT_F5B_REVISION


def load():
    cp = json.loads((FIXTURE / "control_plane_run.json").read_text())
    proposal = json.loads((FIXTURE / "proposal.json").read_text())
    executor = json.loads((FIXTURE / "executor.json").read_text())
    executor["repository"]["revision"] = EXECUTOR_REVISION
    executor["provenance"]["source_asserted"]["repository_revision"] = EXECUTOR_REVISION
    return cp, proposal, executor


def run(cp, proposal, executor):
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=executor, control_plane_revision=REVISION)


def rejects(mutate, match=None):
    cp, proposal, executor = load()
    mutate(cp, executor)
    with pytest.raises(ImportContractError, match=match):
        run(cp, proposal, executor)


def test_clean_fixture_is_accepted_and_complete():
    bundle = run(*load())
    assert bundle.status == "reconstruction_complete"


# ---- executor export rows -----------------------------------------------------------------------

@pytest.mark.parametrize("name,mutate,match", [
    ("drop_all", lambda cp, x: x["attempt_events"].clear(), "has no attempt events"),
    ("drop_first", lambda cp, x: x["attempt_events"].pop(0), "do not start with attempted"),
    ("drop_last", lambda cp, x: x["attempt_events"].pop(-1), "contradicts the terminal attempt event"),
    ("duplicate_first", lambda cp, x: x["attempt_events"].insert(1, copy.deepcopy(x["attempt_events"][0])), "repeated or out of order"),
    ("duplicate_last", lambda cp, x: x["attempt_events"].append(copy.deepcopy(x["attempt_events"][-1])), "repeated or out of order"),
    ("swap_first_two", lambda cp, x: x["attempt_events"].reverse(), "repeated or out of order"),
    ("corrupt_terminal_status", lambda cp, x: x["attempt_events"][-1].__setitem__("status", "unknown"), "contradicts the terminal attempt event"),
    ("corrupt_time_order", lambda cp, x: x["attempt_events"][-1].__setitem__("created_at", x["attempt_events"][0]["created_at"] - 1), "out of order"),
])
def test_attempt_events_must_be_complete_ordered_and_consistent(name, mutate, match):
    rejects(mutate, match)


@pytest.mark.parametrize("name,mutate,match", [
    ("duplicate_effect_row", lambda cp, x: x["effects"].append(copy.deepcopy(x["effects"][0])), "duplicate destination effect row"),
    ("duplicate_attempt_row", lambda cp, x: x["attempts"].append(copy.deepcopy(x["attempts"][0])), "duplicate executor attempt row"),
])
def test_duplicate_executor_rows_are_rejected(name, mutate, match):
    rejects(mutate, match)


def test_result_status_must_match_terminal_attempt_event():
    def flip(cp, x):
        x["execution_result"]["status"] = "unknown"
        x["control_plane_evidence"] = x["execution_result"]["control_plane_evidence"]
    rejects(flip, "contradicts the terminal attempt event")


def test_result_cannot_deny_a_newly_acknowledged_effect():
    def flip(cp, x):
        x["execution_result"]["newly_executed"] = False
    rejects(flip, "contradicts the execution result")


# ---- Control Plane journal --------------------------------------------------------------------

def test_journal_attempt_lifecycle_requires_a_single_start_record():
    rejects(lambda cp, x: cp["attempts"].pop(0), "lacks its attempted start record")
    rejects(lambda cp, x: cp["attempts"].insert(1, copy.deepcopy(cp["attempts"][0])), "repeats a record")
    rejects(lambda cp, x: cp["attempts"].append(copy.deepcopy(cp["attempts"][-1])), "repeats a record")


@pytest.mark.parametrize("reorder", [lambda r: r.reverse(), lambda r: r.insert(0, r.pop(1))])
def test_resolution_checks_must_follow_journal_completion_order(reorder):
    rejects(lambda cp, x: reorder(cp["resolution_checks"]), "out of journal order")


def _uncertain_run():
    """Journal whose attempt is left 'unknown' while a later accepted observation shows the effect applied."""
    cp, proposal, _ = load()
    cp["attempts"][-1] = dict(cp["attempts"][-1], status="unknown", acknowledgement={}, error="destination_outcome_unknown")
    applied = next(r for r in cp["reconciliations"] if r["observation"]["state"] == "applied")
    closeout = {"attempt_id": cp["attempts"][-1]["attempt_id"], "effect_id": applied["effect_id"], "original_status": "unknown",
                "observed_state": "applied", "observed_at": applied["observation"]["observed_at"], "reconciled_at": applied["reconciled_at"]}
    return cp, proposal, closeout


def test_uncertain_attempt_requires_closeout_for_accepted_observation():
    cp, proposal, closeout = _uncertain_run()
    with pytest.raises(ImportContractError, match="lacks closeout"):
        validate_run(cp, proposal, runtime_authority=True)
    cp["closeouts"] = [closeout]
    validate_run(cp, proposal, runtime_authority=True)  # the recorded closeout satisfies the rule


def test_duplicate_closeout_is_rejected():
    cp, proposal, closeout = _uncertain_run()
    cp["closeouts"] = [closeout, copy.deepcopy(closeout)]
    with pytest.raises(ImportContractError, match="duplicate attempt closeout"):
        validate_run(cp, proposal, runtime_authority=True)
