"""Component-local regressions for runtime-authority journal and acknowledgement handling.

The fixture in tests/fixtures/security_runtime_valid/ is byte-identical to the
native output of a LOCAL re-run of the cognous-stack-qualification
security-runtime suite case `test_effect_and_commit_boundar0` (the valid case of
test_effect_and_commit_boundary) at the base pins (Control Plane 996baeb4,
runtime fd6b76fa, Replay 3601fb21; synthetic data only). It is not part of the
hosted, archived F3 qualification evidence.

The F5b generation (Control Plane a34c3dc2, runtime 4a83b175) is a separate,
additive mapping; the fd6b76fa / 996baeb4 generation stays accepted, so this
fixture is kept unchanged and is reused for both generations by rewriting only
the executor's source-asserted revision. Native F5b-pin output is exercised by
cognous-stack-qualification/suites/security-runtime.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

FIXTURE = Path(__file__).parent / "fixtures" / "security_runtime_valid"
JOURNAL_REVISIONS = [I.CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, I.CONTROL_PLANE_SECURITY_REVISION,
                     I.CONTROL_PLANE_F5B_REVISION]
PAIRS = {
    "merged": (I.CONTROL_PLANE_MERGED_REVISION, I.MOLTBOT_MERGED_REVISION),
    "refusal": (I.CONTROL_PLANE_REFUSAL_REVISION, I.MOLTBOT_REFUSAL_REVISION),
    "runtime_authority": (I.CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION, I.MOLTBOT_RUNTIME_AUTHORITY_REVISION),
    "security": (I.CONTROL_PLANE_SECURITY_REVISION, I.MOLTBOT_SECURITY_REVISION),
    "f5b_security": (I.CONTROL_PLANE_F5B_REVISION, I.MOLTBOT_F5B_REVISION),
}
EXECUTOR = dict(PAIRS.values())


def load(executor_revision=I.MOLTBOT_SECURITY_REVISION):
    cp = json.loads((FIXTURE / "control_plane_run.json").read_text())
    proposal = json.loads((FIXTURE / "proposal.json").read_text())
    executor = json.loads((FIXTURE / "executor.json").read_text())
    executor["repository"]["revision"] = executor_revision
    executor["provenance"]["source_asserted"]["repository_revision"] = executor_revision
    return cp, proposal, executor


def run(cp, proposal, executor, revision):
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=executor,
                                   control_plane_revision=revision)


@pytest.mark.parametrize("revision", JOURNAL_REVISIONS)
def test_completed_journal_fixture_remains_complete(revision):
    cp, proposal, executor = load(EXECUTOR[revision])
    bundle = run(cp, proposal, executor, revision)
    assert bundle.status == "reconstruction_complete"
    assert not any(f.code == "B006" for f in bundle.import_reports[0].findings)


@pytest.mark.parametrize("revision", JOURNAL_REVISIONS)
@pytest.mark.parametrize("terminal", [None, "interrupted"])
def test_unfinished_journal_check_makes_reconstruction_partial(revision, terminal):
    cp, proposal, executor = load(EXECUTOR[revision])
    opening = copy.deepcopy(cp["check_events"][0])
    assert opening["phase"] == "opened"
    opening["check_id"] = "unfinished-check"
    cp["check_events"].append(opening)
    if terminal:
        cp["check_events"].append(dict(opening, phase=terminal, reasons=["check_interrupted"]))
    bundle = run(cp, proposal, executor, revision)
    assert bundle.status == "reconstruction_partial"
    report = bundle.import_reports[0]
    assert report.complete is False
    finding = next(f for f in report.findings if f.code == "B006")
    assert "unfinished-check" in finding.message and finding.value_state == "unknown"
    # The unfinished journal is still retained as original source evidence.
    events = [r.data for r in bundle.records if r.record_type == "resolution_check_event"]
    assert events == cp["check_events"]


@pytest.mark.parametrize("revision", JOURNAL_REVISIONS)
def test_completed_journals_cannot_reuse_one_resolution_check(revision):
    cp, proposal, executor = load(EXECUTOR[revision])
    first = cp["check_events"][0]["check_id"]
    sibling = [dict(copy.deepcopy(e), check_id="sibling-check") for e in cp["check_events"] if e["check_id"] == first]
    cp["check_events"].extend(sibling)
    with pytest.raises(ImportContractError, match="reuse one actual resolution check"):
        run(cp, proposal, executor, revision)
    # A separately recorded check with a different producer UUID substantiates it.
    stage = sibling[0]["stage"]
    check = copy.deepcopy(next(x for x in cp["resolution_checks"] if x["stage"] == stage))
    check["check_id"] = "separately-recorded-check"
    cp["resolution_checks"].append(check)
    assert run(cp, proposal, executor, revision).status == "reconstruction_complete"


@pytest.mark.parametrize("pair", sorted(PAIRS))
def test_dangling_acknowledgement_fails_closed_for_all_v2_profiles(pair):
    revision, executor_revision = PAIRS[pair]
    cp, proposal, executor = load(executor_revision)
    run(cp, proposal, executor, revision)
    cp["attempts"][0]["acknowledgement"] = {"attempt_id": "executor-attempt-missing"}
    with pytest.raises(ImportContractError, match="dangling or ambiguous"):
        run(cp, proposal, executor, revision)


def test_f5b_generation_is_separate_and_attributed():
    cp, proposal, executor = load(I.MOLTBOT_F5B_REVISION)
    bundle = run(cp, proposal, executor, I.CONTROL_PLANE_F5B_REVISION)
    assert bundle.status == "reconstruction_complete"
    assert {p.profile_id for p in bundle.producer_profiles} >= {I.BOUNDED_F5B_PROFILE, I.MOLTBOT_F5B_PROFILE}
    assert bundle.metadata["manifest_revision"] == I.MANIFEST_F5B_REVISION
    assert bundle.metadata["executor_failure_reference_verification"] == "source_asserted_not_independently_verified"
    # The historical security generation keeps its own attribution.
    cp, proposal, executor = load(I.MOLTBOT_SECURITY_REVISION)
    bundle = run(cp, proposal, executor, I.CONTROL_PLANE_SECURITY_REVISION)
    assert bundle.metadata["manifest_revision"] == I.MANIFEST_SECURITY_REVISION
    assert I.BOUNDED_SECURITY_PROFILE in {p.profile_id for p in bundle.producer_profiles}


@pytest.mark.parametrize("cp_revision, executor_revision", [
    (I.CONTROL_PLANE_SECURITY_REVISION, I.MOLTBOT_F5B_REVISION),
    (I.CONTROL_PLANE_F5B_REVISION, I.MOLTBOT_SECURITY_REVISION),
    (I.CONTROL_PLANE_F5B_REVISION, I.MOLTBOT_RUNTIME_AUTHORITY_REVISION),
])
def test_f5b_generation_rejects_cross_generation_pairs(cp_revision, executor_revision):
    cp, proposal, executor = load(executor_revision)
    with pytest.raises(ImportContractError, match="revision combination"):
        run(cp, proposal, executor, cp_revision)
