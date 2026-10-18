"""Input validation: with a proposal and no executor export, a journal observation's destination_state is compared to the
operation the proposal commits to (target, amount, unit, payload, grant, effect)."""
import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError, import_bounded_workflow
from agent_replay_bundle.importers import CONTROL_PLANE_P2_REVISION

PAIRED = Path(__file__).parent / "fixtures" / "programme2_paired"
SCENARIOS = sorted(p.name for p in PAIRED.iterdir() if p.is_dir())


def load(name):
    return [json.loads((PAIRED / name / f"{f}.json").read_text()) for f in ("control_plane_run", "proposal", "executor")]


def destinations(node):
    if isinstance(node, dict):
        if isinstance(node.get("destination_state"), dict) and node["destination_state"]:
            yield node["destination_state"]
        for value in node.values():
            yield from destinations(value)
    elif isinstance(node, list):
        for value in node:
            yield from destinations(value)


def bump(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value + 1000
    return {"x": 1} if isinstance(value, dict) else str(value) + "-x"


def journal_only(cp, proposal):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CONTROL_PLANE_P2_REVISION)


@pytest.mark.parametrize("name", SCENARIOS)
def test_control_every_paired_capture_imports_without_an_export_with_unchanged_status(name):
    cp, proposal, executor = load(name)
    bundle = journal_only(cp, proposal)
    assert bundle.status == "reconstruction_partial"
    assert [f.code for f in bundle.import_reports[0].findings if f.code == "B004"] == ["B004"]
    # the same record with no proposal at all is unchanged too
    assert import_bounded_workflow(copy.deepcopy(cp), control_plane_revision=CONTROL_PLANE_P2_REVISION).status == "reconstruction_partial"


@pytest.mark.parametrize("field", ["target", "amount", "unit", "payload", "grant_id", "effect_id"])
@pytest.mark.parametrize("name", SCENARIOS)
def test_a_changed_destination_state_member_is_refused_without_an_export(name, field):
    cp, proposal, _ = load(name)
    changed = 0
    for d in destinations(cp):
        if field in d:
            d[field] = bump(d[field])
            changed += 1
    if not changed:
        pytest.skip("this capture carries no destination_state in the journal")
    with pytest.raises(ImportContractError):
        journal_only(cp, proposal)
