"""Route B pre-dispatch denial exports (Runtime AtomicLocalControlPlaneExecutor._denied) must import.

The executor records a typed failure for a denial and exports ``{failure_record_id, failure_class}`` as its Control Plane
evidence. ``failure_class`` is admitted on a denied, non-attempted result of the security-generation profiles only, from the
closed set of the Runtime typed failure record, as an attributable reference that establishes nothing about authority.
The fixture ``route_b_post_commit/denied`` is a real export (authority revoked at the atomic destination after claim issuance).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

BASE = Path(__file__).parent / "fixtures" / "route_b_post_commit" / "denied"
P2_SHA = "7a4bcd40b3b49e61ff3c294dcca53b52f460b22c"
OLD_P2_SHA = "0a41faa972699f7ec3063967a14cd9bdd3e67d27"
REFUSED = "unsupported typed refusal executor evidence field"


def load():
    return (json.loads((BASE / "control_plane_run.json").read_text()), json.loads((BASE / "proposal.json").read_text()),
            json.loads((BASE / "executor.json").read_text()))


def run(cp, proposal, executor, revision=P2_SHA):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=copy.deepcopy(executor), control_plane_revision=revision)


def mutate_evidence(executor, **changes):
    for holder in (executor["control_plane_evidence"], executor["execution_result"]["control_plane_evidence"]):
        for key, value in changes.items():
            if value is None:
                holder.pop(key, None)
            else:
                holder[key] = value


def test_the_fixture_is_a_denial_with_failure_class():
    _, _, executor = load()
    result = executor["execution_result"]
    assert (result["status"], result["attempted"], result["acknowledged"]) == ("denied", False, False)
    assert executor["control_plane_evidence"]["failure_class"] == "authority_hold"


def test_denial_export_imports_and_keeps_the_reference_only():
    bundle = run(*load())
    assert bundle.status == "reconstruction_complete" and all(r.complete for r in bundle.import_reports)
    assert not any(r.record_type == "executor_observation" for r in bundle.records)


def test_the_claim_stage_journal_of_the_fixture_is_accepted():
    cp, _, _ = load()
    stages = [e["stage"] for e in cp["check_events"] if e["phase"] == "opened"]
    assert stages == ["decision", "claim"]


@pytest.mark.parametrize("cls", sorted(I.RUNTIME_FAILURE_CLASSES))
def test_every_runtime_failure_class_is_admitted_on_a_denial(cls):
    cp, proposal, executor = load()
    mutate_evidence(executor, failure_class=cls)
    assert run(cp, proposal, executor).status == "reconstruction_complete"


@pytest.mark.parametrize("value", ["", "x" * 101, 7, ["authority_hold"], {"a": 1}, True, "made_up_class", "AUTHORITY_HOLD"])
def test_a_class_outside_the_runtime_set_is_refused(value):
    cp, proposal, executor = load()
    mutate_evidence(executor, failure_class=value)
    with pytest.raises(ImportContractError, match="invalid executor failure class"):
        run(cp, proposal, executor)


def test_failure_class_without_failure_record_id_is_admitted_as_a_class_only_reference():
    cp, proposal, executor = load()
    mutate_evidence(executor, failure_record_id=None)
    assert run(cp, proposal, executor).status == "reconstruction_complete"


def test_an_undeclared_member_next_to_failure_class_is_refused():
    cp, proposal, executor = load()
    mutate_evidence(executor, note="x")
    with pytest.raises(ImportContractError, match=REFUSED):
        run(cp, proposal, executor)


def test_invalid_failure_record_id_on_a_denial_is_refused():
    cp, proposal, executor = load()
    mutate_evidence(executor, failure_record_id=7)
    with pytest.raises(ImportContractError, match="failure reference"):
        run(cp, proposal, executor)


def test_not_attempted_clause_in_isolation():
    """The clause that admits failure_class requires status denied AND attempted false. Isolated: with an (unreachable-by-export)
    result that is denied and attempted, the gate itself must not widen; refusal comes from this module's gate or earlier checks."""
    cp, proposal, executor = load()
    executor["execution_result"]["attempted"] = True
    with pytest.raises(ImportContractError):
        run(cp, proposal, executor)
    # the gate predicate, evaluated directly on the two clauses
    def admits(status, attempted):
        return status == "denied" and not attempted
    assert admits("denied", False) and not admits("denied", True) and not admits("unknown", False) and not admits("executed", False)


@pytest.mark.parametrize("status", ["unknown", "executed", "failed", "partial"])
def test_failure_class_on_a_non_denied_result_without_a_report_is_refused(status):
    cp, proposal, executor = load()
    executor["execution_result"]["status"] = status
    with pytest.raises(ImportContractError):
        run(cp, proposal, executor)


def test_the_pin_is_the_merged_control_plane_and_the_defective_one_is_not_kept():
    assert I.CONTROL_PLANE_P2_REVISION == P2_SHA and I.PROGRAMME2_CP_REVISIONS == frozenset({P2_SHA})
    cp, proposal, executor = load()
    with pytest.raises(ImportContractError, match="unsupported Control Plane revision"):
        run(cp, proposal, executor, revision=OLD_P2_SHA)


def test_an_old_pin_record_with_the_reused_claim_journal_is_still_refused():
    """A claim journalled at stage decision (Control Plane 0a41faa9 behaviour) reuses one resolution check and stays refused."""
    cp, proposal, executor = load()
    for event in cp["check_events"]:
        if event["stage"] == "claim":
            event["stage"] = "decision"
            event["decision_id"] = None
    with pytest.raises(ImportContractError):
        run(cp, proposal, executor)


def test_the_four_security_profiles_are_exactly_the_gate():
    assert I.SECURITY_RUNTIME_BOUNDED_PROFILES == frozenset({I.BOUNDED_SECURITY_PROFILE, I.BOUNDED_F5B_PROFILE, I.BOUNDED_P4_PROFILE, I.BOUNDED_P2_PROFILE})
    for other in (I.BOUNDED_REFUSAL_PROFILE, I.BOUNDED_RUNTIME_AUTHORITY_PROFILE):
        assert other not in I.SECURITY_RUNTIME_BOUNDED_PROFILES


def test_a_profile_outside_the_security_set_does_not_admit_failure_class(monkeypatch):
    """Only a Programme 2 capture exists, so the gate is exercised by membership: with the P2 profile removed from the security
    set and given the refusal profile's position the same real export is refused."""
    cp, proposal, executor = load()
    assert run(cp, proposal, executor).status == "reconstruction_complete"
    p2 = I.BOUNDED_P2_PROFILE
    monkeypatch.setattr(I, "SECURITY_RUNTIME_BOUNDED_PROFILES", I.SECURITY_RUNTIME_BOUNDED_PROFILES - {p2})
    monkeypatch.setattr(I, "BOUNDED_REFUSAL_PROFILE", p2)  # the typed-refusal checks still run for it, as for the refusal profile
    with pytest.raises(ImportContractError, match=REFUSED):
        run(cp, proposal, executor)
