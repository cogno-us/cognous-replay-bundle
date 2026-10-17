"""Replay must import the real route-B (atomic local executor) post-commit failure exports (F-24).

Route B reports a post-commit observation failure as result 'unknown' carrying a *recovery report* (the
destination's claim-reconciliation record, keyed by 'status'). The two fixtures in
tests/fixtures/route_b_post_commit/ are exports captured from the runtime at 4a83b175 (AtomicLocalControlPlaneExecutor,
real Control Plane F5b journal, synthetic data): ``observe_bound_fail`` (post-commit read of the bound effect fails ->
recovery status 'applied') and ``lost_ack_recon_down`` (lost acknowledgement and reconciliation also down -> recovery
status 'unknown'). A 'hold' recovery has no live producer path in the captured scenarios; it is planted from the
runtime's recovery module shape.

A recovery report is retained as a report only (record type ``executor_recovery_report``): it never becomes a validated
executor observation, and a result carrying one can only be 'unknown'. Each positive case is paired with negatives.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

BASE = Path(__file__).parent / "fixtures" / "route_b_post_commit"
VARIANTS = ("observe_bound_fail", "lost_ack_recon_down")
RECONCILE = "reconcile_only"


def load(variant):
    d = BASE / variant
    return (json.loads((d / "control_plane_run.json").read_text()),
            json.loads((d / "proposal.json").read_text()),
            json.loads((d / "executor.json").read_text()))


def run(cp, proposal, executor):
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=executor,
                                   control_plane_revision=I.CONTROL_PLANE_P4_REVISION)


def planted(variant, mutate):
    cp, proposal, executor = load(variant)
    mutate(executor)
    return run(cp, proposal, executor)


def rejects(variant, mutate, match):
    with pytest.raises(ImportContractError, match=match):
        planted(variant, mutate)


def _set_observation(x, observation, observed_state=None):
    x["execution_result"]["observation"] = observation
    x["recovery_observations"] = [copy.deepcopy(observation)]
    x["observations"] = []
    if observed_state is not None:
        x["execution_result"]["observed_state"] = observed_state


# ---- the real exports are accepted, and the report is never promoted --------------------------

@pytest.mark.parametrize("variant", VARIANTS)
def test_real_route_b_post_commit_export_imports_complete(variant):
    bundle = run(*load(variant))
    assert bundle.status == "reconstruction_complete"
    assert all(report.complete for report in bundle.import_reports)


@pytest.mark.parametrize("variant", VARIANTS)
def test_recovery_report_is_retained_as_a_report_not_an_observation(variant):
    bundle = run(*load(variant))
    kinds = [r.record_type for r in bundle.records]
    assert "executor_recovery_report" in kinds
    assert "executor_observation" not in kinds
    result = next(r for r in bundle.records if r.record_type == "execution_result")
    assert result.data["status"] == "unknown"
    assert any(f.code == "M021" for report in bundle.import_reports for f in report.findings)


def test_hold_recovery_report_is_accepted_and_establishes_no_destination_state():
    def plant(x):
        effect = x["execution_result"]["effect_id"]
        _set_observation(x, {"status": "hold", "claim_state": "consumed", "retry_eligible": False,
                             "effect_id": effect, "reason": "no_durable_effect_for_claim"}, "unknown")
        x["effects"] = []
    assert planted("observe_bound_fail", plant).status == "reconstruction_complete"


def test_hold_recovery_report_without_a_claim_row_is_accepted():
    def plant(x):
        _set_observation(x, {"status": "hold", "retry_eligible": False, "reason": "claim_unavailable"}, "unknown")
        x["effects"] = []
    assert planted("observe_bound_fail", plant).status == "reconstruction_complete"


# ---- effect-free reconcile: result 'observed' carrying the same recovery report ----------------

def test_effect_free_reconcile_export_imports_complete_and_stays_a_report():
    bundle = run(*load(RECONCILE))
    assert bundle.status == "reconstruction_complete"
    kinds = [r.record_type for r in bundle.records]
    assert "executor_recovery_report" in kinds and "executor_observation" not in kinds


@pytest.mark.parametrize("name,mutate,match", [
    ("claims_an_attempt", lambda x: x["execution_result"].__setitem__("attempted", True), "cannot claim an attempt|attempt"),
    ("claims_acknowledgement", lambda x: x["execution_result"].__setitem__("acknowledged", True), "cannot claim an attempt|acknowledg"),
    ("claims_new_effect", lambda x: x["execution_result"].__setitem__("newly_executed", True), "cannot claim an attempt|new effect"),
    ("observed_state_contradicts_report", lambda x: x["execution_result"].__setitem__("observed_state", "unknown"),
        "observed-state contradiction"),
    ("status_executed_with_report", lambda x: x["execution_result"].__setitem__("status", "executed"),
        "only carried by results unknown or observed|contradicts"),
])
def test_effect_free_reconcile_still_rejects_genuine_defects(name, mutate, match):
    rejects(RECONCILE, mutate, match)


# ---- the neighbouring genuine defects are still rejected --------------------------------------

@pytest.mark.parametrize("name,mutate,match", [
    ("undeclared_member", lambda x: x["execution_result"]["observation"].__setitem__("note", "x") or
        x["recovery_observations"][0].__setitem__("note", "x"), "undeclared members"),
    ("retry_eligible_true", lambda x: x["execution_result"]["observation"].__setitem__("retry_eligible", True) or
        x["recovery_observations"][0].__setitem__("retry_eligible", True), "unsupported retry eligibility"),
    ("wrong_effect", lambda x: x["execution_result"]["observation"].__setitem__("effect_id", "sha256:" + "0" * 64) or
        x["recovery_observations"][0].__setitem__("effect_id", "sha256:" + "0" * 64), "effect_id"),
    ("wrong_operation_digest", lambda x: x["execution_result"]["observation"].__setitem__("operation_digest", "sha256:" + "0" * 64) or
        x["recovery_observations"][0].__setitem__("operation_digest", "sha256:" + "0" * 64), "operation_digest"),
    ("applied_without_operation_digest", lambda x: x["execution_result"]["observation"].pop("operation_digest") and
        x["recovery_observations"][0].pop("operation_digest"), "operation_digest is required"),
    ("observed_state_contradicts_status", lambda x: x["execution_result"].__setitem__("observed_state", "unknown"),
        "observed-state contradiction"),
    ("promoted_to_observed_result", lambda x: x["execution_result"].__setitem__("status", "observed"),
        "cannot claim an attempt|contradicts the terminal attempt event"),
    ("acknowledged_result", lambda x: x["execution_result"].__setitem__("acknowledged", True), "failure reference|contradict"),
    ("terminal_event_dropped", lambda x: x["attempt_events"].pop(-1), "contradicts the terminal attempt event"),
])
def test_applied_recovery_report_still_rejects_genuine_defects(name, mutate, match):
    rejects("observe_bound_fail", mutate, match)


@pytest.mark.parametrize("name,mutate,match", [
    ("unknown_without_reason", lambda x: x["execution_result"]["observation"].pop("reason") and x["recovery_observations"][0].pop("reason"),
        "reason is required"),
    ("status_not_a_recovery_status", lambda x: x["execution_result"]["observation"].__setitem__("status", "absent") or
        x["recovery_observations"][0].__setitem__("status", "absent"), "not a recovery status"),
    ("unknown_claims_applied_state", lambda x: x["execution_result"].__setitem__("observed_state", "applied"),
        "observed-state contradiction"),
])
def test_unknown_recovery_report_still_rejects_genuine_defects(name, mutate, match):
    rejects("lost_ack_recon_down", mutate, match)


@pytest.mark.parametrize("variant", VARIANTS)
@pytest.mark.parametrize("name,mutate,match", [
    ("failure_reference_not_a_string", lambda x: x["control_plane_evidence"].__setitem__("failure_record_id", 7) or
        x["execution_result"]["control_plane_evidence"].__setitem__("failure_record_id", 7), "failure reference"),
    ("unknown_evidence_member", lambda x: x["control_plane_evidence"].__setitem__("extra", 1) or
        x["execution_result"]["control_plane_evidence"].__setitem__("extra", 1), "unsupported typed refusal executor evidence field"),
    ("failure_class_not_a_string", lambda x: x["control_plane_evidence"].__setitem__("failure_class", 7) or
        x["execution_result"]["control_plane_evidence"].__setitem__("failure_class", 7), "failure class"),
])
def test_failure_reference_is_attributable_only_and_typed(variant, name, mutate, match):
    rejects(variant, mutate, match)


def test_failure_class_is_not_admitted_without_a_recovery_report():
    """The extra evidence members are allowed only alongside a recovery report, not on a plain unknown result."""
    def plant(x):
        x["execution_result"].update(observation=None, observed_state="unknown")
        x["observations"] = []
        x.pop("recovery_observations", None)
    rejects("observe_bound_fail", plant, "unsupported typed refusal executor evidence field")


# ---- contract conformance: undeclared members, reconciled marker, extensions (ODES lifecycle contract) -------

from .test_audit_defect_detection import load as _cp_load, rejects as _cp_rejects, run as _cp_run  # noqa: E402


def test_undeclared_member_in_execution_result_is_refused():
    _cp_rejects(lambda cp, x: x["execution_result"].__setitem__("injected_member", 1), "unsupported member")


def test_start_row_marked_reconciled_existing_false_is_refused():
    def plant(cp, x):
        cp["attempts"][0]["acknowledgement"] = {"reconciled_existing": False}
    _cp_rejects(plant, "invalid reconciled_existing marker")


def test_extensions_are_accepted_when_x_prefixed_and_retained_in_the_record():
    cp, proposal, x = _cp_load()
    x["execution_result"]["extensions"] = {"x-syn-vendor.trace": {"span": "abc"}}
    x["extensions"] = {"x-syn-vendor.note": "n"}
    bundle = _cp_run(cp, proposal, x)
    result = next(r for r in bundle.records if r.record_type == "execution_result")
    assert result.data["extensions"] == {"x-syn-vendor.trace": {"span": "abc"}}


@pytest.mark.parametrize("where", ["top", "result"])
@pytest.mark.parametrize("bad", [{"vendor.trace": 1}, {"x-": 1}, []])
def test_extensions_without_x_names_or_not_an_object_are_refused(where, bad):
    def plant(cp, x):
        (x if where == "top" else x["execution_result"])["extensions"] = bad
    _cp_rejects(plant, "extensions")


def test_undeclared_member_outside_extensions_at_top_level_is_still_refused():
    _cp_rejects(lambda cp, x: x.__setitem__("injected_member", 1), "unsupported member")


# ---- F-28: a normal executed route-B export (control_plane_evidence carries the claim and the authority receipt) ----

EXECUTED = "executed"


def _both_evidence(x, fn):
    fn(x["control_plane_evidence"])
    fn(x["execution_result"]["control_plane_evidence"])


def test_real_route_b_normal_execution_export_imports_complete():
    bundle = run(*load(EXECUTED))
    assert bundle.status == "reconstruction_complete"
    assert all(report.complete for report in bundle.import_reports)
    result = next(r for r in bundle.records if r.record_type == "execution_result")
    assert result.data["status"] == "executed"
    assert "executor_recovery_report" not in [r.record_type for r in bundle.records]


@pytest.mark.parametrize("name,mutate,match", [
    ("receipt_other_attempt", lambda x: _both_evidence(x, lambda e: e["authority_receipt"].__setitem__("attempt_id", "other")),
        "authority receipt attempt_id contradicts"),
    ("receipt_other_effect", lambda x: _both_evidence(x, lambda e: e["authority_receipt"].__setitem__("effect_id", "sha256:" + "0" * 64)),
        "authority receipt effect_id contradicts"),
    ("receipt_other_decision", lambda x: _both_evidence(x, lambda e: e["authority_receipt"].__setitem__("decision_id", "other")),
        "authority receipt decision_id contradicts"),
    ("receipt_other_claim", lambda x: _both_evidence(x, lambda e: e["authority_receipt"].__setitem__("claim_id", "claim-2")),
        "authority receipt claim_id contradicts"),
    ("receipt_grant_not_active", lambda x: _both_evidence(x, lambda e: e["authority_receipt"].__setitem__("grant_status", "revoked")),
        "does not show an active grant"),
    ("unsupported_profile", lambda x: _both_evidence(x, lambda e: e.__setitem__("local_authority_effect_profile", "urn:x")),
        "unsupported local authority effect profile"),
    ("claim_not_a_string", lambda x: _both_evidence(x, lambda e: e.__setitem__("claim_id", 7)), "invalid route B claim id"),
    ("linearized_at_not_a_time", lambda x: _both_evidence(x, lambda e: e.__setitem__("linearized_at", "yesterday")),
        "invalid route B linearized_at"),
    ("receipt_missing", lambda x: _both_evidence(x, lambda e: e.pop("authority_receipt")), "incomplete"),
    ("unknown_evidence_member", lambda x: _both_evidence(x, lambda e: e.__setitem__("extra", 1)),
        "unsupported typed refusal executor evidence field"),
    ("receipt_on_a_denied_result", lambda x: x["execution_result"].update(status="denied", attempted=False, acknowledged=False,
                                                                         newly_executed=False),
        "newly executed result|contradict|denied"),
])
def test_route_b_normal_execution_evidence_is_bound_to_the_result(name, mutate, match):
    rejects(EXECUTED, mutate, match)


# ---- step B: the legacy layout, the empty observation and unknown + validated applied are refused -------------------

def test_legacy_layout_recovery_report_in_observations_is_refused():
    def plant(x):
        report = x["execution_result"]["observation"]
        x.pop("recovery_observations")
        x["observations"] = [copy.deepcopy(report)]
    rejects("observe_bound_fail", plant, "not a validated observation")
    cp, proposal, executor = load("observe_bound_fail")
    report = executor["execution_result"]["observation"]
    executor.pop("recovery_observations")
    executor["observations"] = [copy.deepcopy(report)]
    with pytest.raises(ImportContractError) as info:
        run(cp, proposal, executor)
    assert info.value.code == "schema_violation"


@pytest.mark.parametrize("variant", [EXECUTED, "observe_bound_fail", "lost_ack_recon_down", RECONCILE])
def test_empty_observation_object_is_refused(variant):
    cp, proposal, executor = load(variant)
    executor["execution_result"]["observation"] = {}
    with pytest.raises(ImportContractError) as info:
        run(cp, proposal, executor)
    assert info.value.code == "schema_violation"


def test_unknown_result_with_a_validated_applied_observation_is_refused_on_a_real_export():
    """What an older runtime exported for a lost acknowledgement: result unknown, validated applied observation."""
    cp, proposal, executor = load(EXECUTED)
    executor["execution_result"]["status"] = "unknown"
    executor["execution_result"]["acknowledged"] = False
    executor["execution_result"]["newly_executed"] = False
    executor["attempt_events"][-1]["status"] = "unknown"
    with pytest.raises(ImportContractError) as info:
        run(cp, proposal, executor)
    assert info.value.code == "unknown_with_validated_observation"


# ---- real-export scan: no captured export may carry a shape step B refuses -----------------------------------------

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


def test_no_captured_real_export_carries_a_shape_step_b_refuses():
    """Every real executor export captured under tests/fixtures (runtime 3024ef6e) is already in the final layout."""
    seen = 0
    for path in sorted(FIXTURES_ROOT.rglob("executor.json")):
        x = json.loads(path.read_text(encoding="utf-8"))
        result = x["execution_result"]
        seen += 1
        assert result["observation"] != {}, path
        for item in x.get("observations", []):
            assert "state" in item, (path, "a recovery report in observations")
        listed = x.get("recovery_observations")
        if listed is not None:
            assert listed == [result["observation"]], path
        observation = result["observation"]
        if result["status"] == "unknown" and observation and "state" in observation:
            assert observation["state"] not in {"applied", "partial"}, (path, "unknown with a validated applied/partial reading")
    assert seen >= 5
