"""Actual pinned Runtime fixtures; no local stand-in for the producer."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys

import pytest
from agent_replay_bundle import recovery_inspection as ri

if os.environ.get("EXPECTED_IMPORT_ROOT"):
    assert Path(ri.__file__).resolve().is_relative_to(Path(os.environ["EXPECTED_IMPORT_ROOT"]))

RUNTIME = Path(os.environ["COGNOUS_RUNTIME_SOURCE"]).resolve()
PINNED_BLOBS = {
    "engine/recovery_resolution.py": "463a8814a4b61ab79ba78482b25e9c6c7fdf47a2",
    "engine/revocation_closeout.py": "5488756e685998c4b65a8eab3742a5ea0e2ecff1",
}
for relative, expected in PINNED_BLOBS.items():
    data = (RUNTIME / relative).read_bytes().rstrip(b"\n") + b"\n"
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == expected
sys.path.insert(0, str(RUNTIME))
from engine.recovery_resolution import SyntheticObservation, SyntheticRecoveryLedger
from engine.revocation_closeout import OrderingEvidence, RevocationCloseoutStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


@pytest.fixture
def ledger(tmp_path):
    old = RevocationCloseoutStore(tmp_path, clock=lambda: NOW)
    old.record_item(effect_id="effect", attempt_id="attempt", decision_id="decision", grant_id="grant",
                    grant_revision="r1", state="executing", ordering=OrderingEvidence(1, "synthetic:queue"))
    old.record_revocation(grant_id="grant", grant_revision="r1", revocation=OrderingEvidence(2, "synthetic:revocation"),
                          owner="synthetic:owner", deadline=NOW-timedelta(hours=1),
                          reconciliation_ref="synthetic:reconciliation")
    return old, SyntheticRecoveryLedger(old.path, synthetic=True, clock=lambda: NOW)


def observation(**changes):
    return replace(SyntheticObservation(event_id="event-1", effect_id="effect", attempt_id="attempt",
        adapter_id="synthetic:adapter", client_reference="synthetic:client", state="unknown", observed_at=NOW,
        ordering_domain="synthetic:domain", order=3, observation_ref="synthetic:observation",
        observation_digest="0"*64, observer_ref="synthetic:observer", watermark_ref="synthetic:watermark",
        provider_acceptance_ref="synthetic:unavailable", evidence_location_ref="synthetic:café"), **changes)


def append(pair, **changes):
    current = pair[1].current("attempt")
    return pair[1].append(observation(**changes), expected_revision=current["revision"],
                          predecessor_digest=current["head_digest"])


def export(pair):
    return pair[1].export_attempt(effect_id="effect", attempt_id="attempt")


def identity(source):
    return {k: source["original"][k] for k in ri.IDENTITY}


def inspect(source, module=ri):
    return module.import_recovery_inspection(source, runtime_revision=ri.RUNTIME_REVISION,
                                              expected_identity=identity(source))


def test_empty_export_is_non_effecting_and_deterministic(ledger):
    before = export(ledger)
    result = inspect(before)
    assert result == inspect(before)
    assert result["source"] == before == export(ledger)
    assert result["source"]["current"]["work_state"] == "awaiting_observation"
    assert result["loss_report"]["dropped_fields"] == []
    ri.validate_recovery_inspection(result)
    result["source"]["original"]["effect_id"] = "changed"
    assert before == export(ledger)


@pytest.mark.parametrize("state,coverage,final,work", [
    ("unknown", False, False, "awaiting_finality"), ("absent", True, True, "awaiting_finality"),
    ("partial", True, True, "partial_followup"), ("applied", False, True, "awaiting_finality"),
    ("applied", True, False, "awaiting_finality"), ("applied", True, True, "resolved")])
def test_outcome_is_not_authority_or_settlement(ledger, state, coverage, final, work):
    append(ledger, state=state, complete_coverage=coverage, final=final)
    result = inspect(export(ledger))
    assert result["source"]["current"]["work_state"] == work
    assert result["assurance"]["settlement_verified"] is False
    assert result["assurance"]["retry_eligible"] is False
    ri.validate_recovery_inspection(result)


def test_partial_then_applied_retains_history(ledger):
    append(ledger, state="partial")
    append(ledger, event_id="event-2", order=4, state="applied", final=True, complete_coverage=True)
    result = inspect(export(ledger))
    assert len(result["source"]["events"]) == 2
    assert result["source"]["current"]["work_state"] == "resolved"
    assert all(c["digest_check"] == "matched_supplied_canonical_bytes" for c in result["event_checks"])


def test_collision_gap_and_duplicate_after_permanent_hold(ledger):
    first = append(ledger)
    append(ledger, state="partial", order=4)  # same ID, different admission envelope
    append(ledger, event_id="event-3", state="applied", order=5, final=True, complete_coverage=True)
    duplicate = ledger[1].append(observation(), expected_revision=0, predecessor_digest=None)
    assert duplicate["admission"] == first["admission"]
    assert duplicate["current"]["work_state"] == "conflict_review"
    result = inspect(export(ledger))
    assert len(result["source"]["events"]) == 3
    assert result["event_checks"][1]["digest_check"] == "not_performed_missing_preimage"
    assert result["loss_report"]["unavailable_evidence"][0]["path"] == "events[1].body"
    assert result["loss_report"]["full_payload_reconstruction"] == "unavailable"
    ri.validate_recovery_inspection(result)


def test_new_id_disagreement_has_available_digest(ledger):
    append(ledger, state="applied", final=True, complete_coverage=True)
    append(ledger, event_id="event-2", order=4)
    result = inspect(export(ledger))
    assert result["source"]["current"]["work_state"] == "conflict_review"
    assert result["loss_report"]["unavailable_evidence"] == []
    ri.validate_recovery_inspection(result)


@pytest.mark.parametrize("state", ["applied", "absent", "partial"])
def test_legacy_remains_unverified_and_does_not_resolve_work(ledger, state):
    ledger[0].close_original_attempt(attempt_id="attempt", observation_state=state,
        observation=OrderingEvidence(3, "synthetic:legacy"), observation_ref="synthetic:legacy")
    result = inspect(export(ledger))
    assert len(result["loss_report"]["unavailable_evidence"]) == 6
    assert result["source"]["current"]["work_state"] == "awaiting_observation"
    ri.validate_recovery_inspection(result)


def set_path(obj, path, value):
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value


@pytest.mark.parametrize("path,value", [
    (("profile",), "unsupported"), (("export_format",), "unsupported"),
    (("limitations",), []), (("disposition", "status"), "resolved"),
    (("disposition", "grant_id"), "other"), (("original", "attempt_id"), "other"),
    (("events",), []), (("events", 0, "revision"), True),
    (("events", 0, "digest"), "a"*64),
    (("events", 0, "body", "predecessor_digest"), "a"*64),
    (("events", 0, "body", "observation", "state"), "applied"),
    (("events", 0, "admission", "identity", "grant_id"), "other"),
    (("events", 0, "admission", "checks", "independent_verification"), "verified"),
    (("events", 0, "admission", "freshness_age_seconds"), -1),
    (("current", "work_state"), "resolved"), (("current", "settlement_verified"), True),
    (("current", "retry_eligible"), True), (("current", "revision"), 10),
])
def test_bad_export_rejected(ledger, path, value):
    append(ledger)
    source = export(ledger)
    selected = identity(source)
    set_path(source, path, value)
    with pytest.raises(ri.RecoveryInspectionError):
        ri.import_recovery_inspection(source, runtime_revision=ri.RUNTIME_REVISION, expected_identity=selected)


def test_wrong_revision_duplicate_events_and_missing_identity_rejected(ledger):
    append(ledger)
    source = export(ledger)
    with pytest.raises(ri.RecoveryInspectionError):
        ri.import_recovery_inspection(source, runtime_revision="main", expected_identity=identity(source))
    with pytest.raises(ri.RecoveryInspectionError):
        ri.import_recovery_inspection(source, runtime_revision=ri.RUNTIME_REVISION, expected_identity={})
    source["events"].append(deepcopy(source["events"][0]))
    with pytest.raises(ri.RecoveryInspectionError):
        inspect(source)


@pytest.mark.parametrize("section,field", [("original", "ordering_ref"), ("disposition", "deadline"),
    ("disposition", "owner"), ("disposition", "reconciliation_ref")])
def test_missing_original_evidence_not_silently_accepted(ledger, section, field):
    source = export(ledger)
    del source[section][field]
    with pytest.raises(ri.RecoveryInspectionError):
        inspect(source)


@pytest.mark.parametrize("field,value", [("loss_report", {}), ("event_checks", []),
    ("source_content_sha256", "a"*64), ("assurance", {"settlement_verified": True})])
def test_native_result_tampering_rejected(ledger, field, value):
    append(ledger)
    result = inspect(export(ledger))
    result[field] = value
    with pytest.raises(ri.RecoveryInspectionError):
        ri.validate_recovery_inspection(result)


def test_dispatch_guard_rejects_unknown_export(ledger):
    source = export(ledger)
    source["export_format"] = "unsupported"
    with pytest.raises(ri.RecoveryInspectionError):
        inspect(source)


def test_loss_guard_preserves_collision_gap(ledger):
    append(ledger)
    append(ledger, order=4, state="partial")
    assert inspect(export(ledger))["loss_report"]["unavailable_evidence"]


@pytest.mark.parametrize("mutation", ["profile", "loss"])
def test_disposable_guard_mutation_is_detected(tmp_path, mutation):
    package = Path(ri.__file__).parent
    root = tmp_path / "isolated"
    shutil.copytree(package, root / "agent_replay_bundle", ignore=shutil.ignore_patterns("__pycache__"))
    test = root / "checks.py"
    shutil.copyfile(__file__, test)
    module = root / "agent_replay_bundle" / "recovery_inspection.py"
    code = module.read_text()
    if mutation == "profile":
        target = 'source["profile"] == PROFILE and source["export_format"] == EXPORT_FORMAT'
        changed = code.replace(target, "True", 1)
        case = "test_dispatch_guard_rejects_unknown_export"
    else:
        target = '"unavailable_evidence": gaps'
        changed = code.replace(target, '"unavailable_evidence": []', 1)
        case = "test_loss_guard_preserves_collision_gap"
    assert changed != code
    env = dict(os.environ, PYTHONPATH=str(root), EXPECTED_IMPORT_ROOT=str(root))
    command = [sys.executable, "-m", "pytest", "-q", str(test) + "::" + case]
    baseline = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    module.write_text(changed)
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache)
    mutant = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=30)
    assert mutant.returncode == 1, mutant.stdout + mutant.stderr
    assert "1 failed" in mutant.stdout and case in mutant.stdout
