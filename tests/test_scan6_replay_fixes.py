"""Scan-6 fixes: strict retry_eligible in the W3 atomic importer (S6-C-01) and non-finite numbers (S6-C-02)."""
import pytest

from agent_replay_bundle.importers import ImportContractError, _validate_executor_attempt_rows
from agent_replay_bundle.ingress import NonFiniteNumberError, load_json_bounded
from agent_replay_bundle.loader import load_replay_bundle
from agent_replay_bundle.w3_atomic_import import (
    AtomicEvidenceContractError, W2_RUNTIME_REVISION, import_w2_atomic_failure_history,
)


def _import(observation):
    return import_w2_atomic_failure_history(
        runtime_revision=W2_RUNTIME_REVISION, effect_id="effect-1", decision_id="decision-1",
        failure_records=[], attempt_records=[], observation=observation)


@pytest.mark.parametrize("value", [1, "true", "yes", "false", 0, [], {}, None, [1], 2.5])
def test_w3_retry_eligible_non_false_refused(value):
    with pytest.raises(AtomicEvidenceContractError):
        _import({"status": "hold", "retry_eligible": value})


def test_w3_retry_eligible_false_still_accepted():
    assert _import({"status": "hold", "retry_eligible": False}).records[-1].data["retry_eligible"] is False


def _source(times):
    events = [{"event_id": i + 1, "created_at": t, "attempt_id": "a1",
               "status": "attempted" if i == 0 else "executed"} for i, t in enumerate(times)]
    return {"attempts": [{"attempt_id": "a1"}], "attempt_events": events}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("pos", [0, 1, 2])
def test_ordering_refuses_non_finite_created_at(bad, pos):
    times = [1.0, 2.0, 3.0]
    times[pos] = bad
    with pytest.raises(ImportContractError) as ei:
        _validate_executor_attempt_rows(_source(times), {"a1": {"attempt_id": "a1"}})
    assert ei.value.code == "event_order"


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_load_json_bounded_rejects_non_finite(tmp_path, token):
    p = tmp_path / "x.json"
    p.write_text('{"created_at": %s}' % token)
    with pytest.raises(NonFiniteNumberError):
        load_json_bounded(p)
    with pytest.raises(ValueError):
        load_replay_bundle(p)
