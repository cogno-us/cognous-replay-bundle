"""Lifecycle contract conformance: attempt transitions, result binding and matrix, and schema checks.

Regression tests for the importer behaviour added with the lifecycle contract re-vendor (ODES e5fe3822). The vendored
reference validator is the oracle wherever it models the rule: transition tables, the result status matrix.
Synthetic data only.
"""
from __future__ import annotations

import copy
import itertools
import sys

import pytest

from . import test_contract_lifecycle_conformance as C
from agent_replay_bundle import importers as I
from agent_replay_bundle import programme2_profiles as P2
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

REF = sys.modules["odes_lifecycle_reference_validator"]  # loaded by the conformance module from the vendored source

EXECUTOR_STATUSES = sorted(I.ATTEMPT_EVENT_STATUSES)
CP_STATUSES = sorted(I.CONTROL_PLANE_ATTEMPT_STATUSES)


# ---- attempt state machines ------------------------------------------------------------------------------

def test_transition_tables_equal_the_vendored_contract():
    assert I.EXECUTOR_ATTEMPT_TRANSITIONS == REF.EXECUTOR_TRANSITIONS
    assert I.CONTROL_PLANE_ATTEMPT_TRANSITIONS == REF.CONTROL_PLANE_TRANSITIONS
    assert set(I.EXECUTOR_ATTEMPT_TRANSITIONS) == set(EXECUTOR_STATUSES)
    assert set(I.CONTROL_PLANE_ATTEMPT_TRANSITIONS) == set(CP_STATUSES)


def _executor_events(*statuses):
    return [{"event_id": n, "attempt_id": "a1", "status": status, "error": None, "created_at": 1000.0 + n}
            for n, status in enumerate(statuses, 1)]


def _executor_source(*statuses):
    return {"attempts": [{"attempt_id": "a1"}], "attempt_events": _executor_events(*statuses)}


@pytest.mark.parametrize("prev,nxt", list(itertools.product(EXECUTOR_STATUSES, EXECUTOR_STATUSES)))
def test_executor_event_transitions_follow_the_contract(prev, nxt):
    if nxt == "attempted":
        return  # a repeated start is repeated_start_event, covered by the vendored fixtures
    statuses = ("attempted", nxt) if prev == "attempted" else ("attempted", prev, nxt)
    source = _executor_source(*statuses)
    allowed = nxt in I.EXECUTOR_ATTEMPT_TRANSITIONS[prev]
    if allowed:
        I._validate_executor_attempt_rows(source, {"a1": source["attempts"][0]})
    else:
        with pytest.raises(ImportContractError) as info:
            I._validate_executor_attempt_rows(source, {"a1": source["attempts"][0]})
        assert info.value.code == "attempt_transition"


def test_a_closed_executor_attempt_is_never_reopened():
    for closed in ("failed", "denied", "reconciled"):
        for later in ("executed", "partial", "unknown", "failed", "denied", "reconciled"):
            source = _executor_source("attempted", closed, later)
            with pytest.raises(ImportContractError) as info:
                I._validate_executor_attempt_rows(source, {"a1": source["attempts"][0]})
            assert info.value.code == "attempt_transition", (closed, later)


def _cp_row(status, **extra):
    return {"attempt_id": "c1", "effect_id": "e1", "decision_id": "d1", "started_at": "2026-01-01T00:00:00Z",
            "status": status, "acknowledgement": {}, "error": None, **extra}


def _cp_run(rows):
    return {"attempts": rows, "reconciliations": [], "observations": []}


def _contract_codes_for_cp(rows):
    return {v.code for v in REF.validate({"contract": "execution-attempt-lifecycle", "contract_version": "0.1.0-draft",
                                          "producer": "control-plane", "control_plane_attempts": rows})}


@pytest.mark.parametrize("prev,nxt", [(p, n) for p in CP_STATUSES for n in CP_STATUSES if p != n])
def test_control_plane_row_transitions_follow_the_contract(prev, nxt):
    last = _cp_row(nxt, error="again") if nxt == "attempted" else _cp_row(nxt)  # not a verbatim repeat of the start row
    rows = [_cp_row("attempted"), last] if prev == "attempted" else [_cp_row("attempted"), _cp_row(prev), last]
    allowed = nxt in I.CONTROL_PLANE_ATTEMPT_TRANSITIONS[prev]
    assert ("attempt_transition" not in _contract_codes_for_cp(rows)) == allowed
    if prev == "attempted":
        if allowed:
            I._validate_repaired_run(_cp_run(rows))
        else:
            with pytest.raises(ImportContractError) as info:
                I._validate_repaired_run(_cp_run(rows))
            assert info.value.code == "attempt_transition"
    elif not allowed:
        with pytest.raises(ImportContractError) as info:
            I._validate_repaired_run(_cp_run(rows))
        assert info.value.code == "attempt_transition"


@pytest.mark.parametrize("closed", ["acknowledged", "partial", "failed"])
def test_a_closed_control_plane_attempt_gets_no_later_row(closed):
    rows = [_cp_row("attempted"), _cp_row(closed), _cp_row("attempted", error="again")]
    with pytest.raises(ImportContractError) as info:
        I._validate_repaired_run(_cp_run(rows))
    assert info.value.code == "attempt_transition"


@pytest.mark.parametrize("member,value", [("effect_id", "e2"), ("decision_id", "d2")])
def test_control_plane_attempt_identity_is_fixed_by_the_first_row(member, value):
    rows = [_cp_row("attempted"), _cp_row("acknowledged", **{member: value})]
    assert "attempt_identity_changed" in _contract_codes_for_cp(rows)
    with pytest.raises(ImportContractError) as info:
        I._validate_repaired_run(_cp_run(rows))
    assert info.value.code == "attempt_identity_changed"


def test_a_normal_control_plane_lifecycle_is_unchanged():
    for last in ("acknowledged", "partial", "failed", "unknown"):
        I._validate_repaired_run(_cp_run([_cp_row("attempted"), _cp_row(last)]))
    I._validate_repaired_run(_cp_run([_cp_row("attempted")]))


# ---- result status matrix --------------------------------------------------------------------------------

def _grid():
    observations = [None,
                    {"effect_id": "e", "state": "applied"}, {"effect_id": "e", "state": "partial"},
                    {"effect_id": "e", "state": "absent"}, {"effect_id": "e", "state": "unknown"},
                    {"status": "applied", "retry_eligible": False}, {"status": "hold", "retry_eligible": False}]
    flag = [True, False]
    for status, state, obs in itertools.product(
            ["failed", "partial", "unknown", "executed", "reconciled", "observed", "denied"],
            ["applied", "partial", "absent", "unknown", "bogus"], observations):
        for attempted, acknowledged, fresh in itertools.product(flag, flag, flag):
            yield {"status": status, "attempt_id": "a1", "observed_state": state, "observation": obs,
                   "attempted": attempted, "acknowledged": acknowledged, "newly_executed": fresh}
        yield {"status": status, "attempt_id": "a1", "observed_state": state, "observation": obs}  # flags absent


def test_result_status_matrix_equals_the_vendored_rule_over_a_grid():
    checked = 0
    for result in _grid():
        assert I._result_matrix_problems(result) == REF.result_matrix_problems(result), result
        checked += 1
    assert checked > 2000


def test_result_matrix_refuses_a_non_boolean_flag():
    result = {"status": "executed", "attempt_id": "a1", "observed_state": "applied", "attempted": 1,
              "acknowledged": True, "newly_executed": True, "observation": {"effect_id": "e", "state": "applied"}}
    assert I._result_matrix_problems(result) == REF.result_matrix_problems(result) != []


def test_matrix_violation_is_refused_with_its_code_even_without_control_plane_evidence():
    """An executed result that is not a fresh execution is refused by the matrix itself."""
    doc = copy.deepcopy(C.FIXTURES["result-state-matrix-executed-not-fresh"]["document"])
    outcome = C.evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "result_state_matrix", outcome.message
    # the same record whose producer acknowledgement agrees with the result is still refused by the matrix: the rule
    # does not depend on the Control Plane acknowledgement cross-check
    cp, proposal, x = C.load_security()
    x["execution_result"]["newly_executed"] = False
    x["control_plane_attempts"][0]["acknowledgement"]["newly_executed"] = False
    x["control_plane_evidence"]["attempt"] = x["control_plane_attempts"][0]
    x["execution_result"]["control_plane_evidence"] = x["control_plane_evidence"]
    with pytest.raises(ImportContractError) as info:
        import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=C.REVISION)
    assert info.value.code == "result_state_matrix", str(info.value)


# ---- result attempt binding ------------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["failed", "partial", "unknown", "executed", "reconciled"])
@pytest.mark.parametrize("named", [None, "syn-unregistered-attempt"])
def test_a_status_that_claims_an_attempt_must_name_a_row_of_the_export(status, named):
    base = {"failed": "result-failed-null-attempt-id", "partial": "result-partial-null-attempt-id",
            "executed": "result-executed-null-attempt-id", "reconciled": "result-reconciled-null-attempt-id",
            "unknown": "executor-unknown-ack-unobserved"}[status]
    doc = copy.deepcopy(C.FIXTURES[base]["document"])
    doc["execution_result"]["attempt_id"] = named
    assert {v.code for v in REF.validate(doc)} == {"result_attempt_unresolved"}
    outcome = C.evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "result_attempt_unresolved", outcome.message


def test_the_binding_follows_the_row_and_event_rules_and_precedes_the_terminal_comparison():
    # a dropped start event keeps its own code even when the result also names no row
    doc = copy.deepcopy(C.FIXTURES["executor-dropped-start-event"]["document"])
    doc["execution_result"]["attempt_id"] = "syn-unregistered-attempt"
    assert C.evaluate_doc(doc).code == "missing_start_event"
    # a terminal-event mismatch is reported as such when the attempt resolves
    doc = copy.deepcopy(C.FIXTURES["executor-terminal-failed-vs-status"]["document"])
    assert C.evaluate_doc(doc).code == "status_terminal_mismatch"


# ---- result binding --------------------------------------------------------------------------------------

@pytest.mark.parametrize("fid", ["result-names-different-decision", "result-names-different-effect",
                                 "observation-names-different-effect"])
def test_result_and_observation_must_name_the_effect_and_decision_of_the_attempt(fid):
    outcome = C.evaluate_doc(copy.deepcopy(C.FIXTURES[fid]["document"]))
    assert not outcome.accepted and outcome.code == "result_binding_mismatch", outcome.message


def test_a_recovery_report_naming_another_effect_is_a_binding_mismatch():
    doc = copy.deepcopy(C.FIXTURES["executor-unknown-recovery-observation-route-b"]["document"])
    doc["execution_result"]["observation"]["effect_id"] = "syn-effect-2"
    assert "result_binding_mismatch" in {v.code for v in REF.validate(doc)}
    outcome = C.evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "result_binding_mismatch", outcome.message


# ---- text and whole-string patterns ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["x\ud800", "\udfffx", "a\udc00b"])
def test_text_that_is_not_valid_unicode_is_refused_in_a_value_or_a_member_name(bad):
    for value in ({"k": bad}, {bad: 1}, {"k": [1, {"n": bad}]}, {"k": (bad,)}):
        with pytest.raises(ImportContractError) as info:
            I._check_record_bounds(value)
        assert info.value.code == "schema_violation"
        assert "not valid Unicode" in str(info.value)


def test_unicode_text_that_is_valid_is_accepted():
    I._check_record_bounds({"k": "café \U0001f600 中文", "é": ["\U0001f600"]})


@pytest.mark.parametrize("where", ["control_plane", "proposal", "export"])
def test_every_importer_input_is_checked_for_invalid_text(where):
    cp, proposal, x = C.load_security()
    {"control_plane": cp, "proposal": proposal, "export": x}[where]["injected"] = "x\ud800"
    with pytest.raises(ImportContractError) as info:
        import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=C.REVISION)
    assert info.value.code == "schema_violation" and "not valid Unicode" in str(info.value)


@pytest.mark.parametrize("name", ["x-a\n", "x-abc\n", "x-a.b-c_d\n"])
def test_extension_names_match_the_whole_string(name):
    for pattern in (I.EXTENSION_NAME, P2.EXTENSION_NAME):
        assert pattern.match(name) is None
        assert pattern.match(name.rstrip("\n")) is not None
    with pytest.raises(ImportContractError) as info:
        I._check_extensions({"extensions": {name: 1}}, "test")
    assert info.value.code == "invalid_extension_key"


def test_the_profile_digest_pattern_matches_the_whole_string():
    digest = "sha256:" + "a" * 64
    assert P2.DIGEST.match(digest) is not None
    assert P2.DIGEST.match(digest + "\n") is None
