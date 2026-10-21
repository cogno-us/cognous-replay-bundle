"""A Control Plane decision whose ``result`` is not a value the Control Plane emits is refused, not imported as complete."""
import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import import_bounded_workflow
from agent_replay_bundle import importers as I

P = Path(__file__).parent / "fixtures" / "programme2_paired" / "adapter-default"


def _load():
    return tuple(json.loads((P / n).read_text(encoding="utf-8")) for n in ("control_plane_run.json", "proposal.json", "executor.json"))


def _import(cp, pr, ex):
    return import_bounded_workflow(cp, proposal=pr, moltbot_export=ex, control_plane_revision=I.CONTROL_PLANE_P2_REVISION)


def test_control_authorized_decision_imports_complete():
    cp, pr, ex = _load()
    assert _import(cp, pr, ex).status == "reconstruction_complete"


@pytest.mark.parametrize("value", ["denied", "", "AUTHORIZED", "authorizedx", "allow", None, 7, True, ["authorized"], {"a": 1}])
def test_unknown_decision_result_is_refused(value):
    cp, pr, ex = _load()
    cp["decisions"][0]["result"] = value
    with pytest.raises(I.ImportContractError) as exc:
        _import(cp, pr, ex)
    assert exc.value.code == "unknown_enum_value" and "decisions[0].result" in str(exc.value)


def test_vocabulary_is_the_values_of_every_captured_run():
    assert I.CONTROL_PLANE_DECISION_RESULTS == frozenset({"authorized", "hold"})
