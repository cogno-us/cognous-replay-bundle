"""S2 G2: the executor operation's tenant must equal the authorized proposal's tenant (DEVELOPMENT ONLY, SYNTHETIC / NONPRODUCTION, UNQUALIFIED).

Defect reference: Replay 93a76e28 ``_validate_envelope_chain`` never compared ``execution_envelope.operation.tenant_id``; a coherently rewritten executor operation (export
digests AND the Control Plane observation digest rewritten consistently) with a foreign tenant was ACCEPTED while proposal and decision binding still named tenant-alpha.

Fixture: tests/s2_g2_operation_tenant_fixture is a REAL strict-tenant capture (Control Plane 484fdbd2 + Runtime f7a55e2a Route A, see PROVENANCE.json). The valid
historical tenantless fixtures are tests/fixtures/current_generation. Mutations are in-memory deep copies; digest rewrites use Replay's own canonical digest.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import import_bounded_workflow

FIX = Path(__file__).parent / "s2_g2_operation_tenant_fixture"   # deliberately outside tests/fixtures: the historical golden sweep (golden_legacy_outputs) enumerates every control_plane_run.json under tests/fixtures and asserts the set of EXISTING fixtures is unchanged
CUR = Path(__file__).parent / "fixtures" / "current_generation"
STRICT_LABEL = "484fdbd297235dd24148ddb0703f2055a31eabff"
CUR_LABEL = "b19c47ddd020409d24e52e70b11359c46265edbb"
ALPHA = "tenant-alpha"
FILES = ("control_plane_run.json", "proposal.json", "runtime_export.json")


def load(directory):
    return tuple(json.loads((directory / f).read_text()) for f in FILES)


def run(cp, proposal, export, label=STRICT_LABEL):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=copy.deepcopy(export), control_plane_revision=label)


def _replace(node, old, new):
    if isinstance(node, dict):
        for k, val in list(node.items()):
            node[k] = new if val == old else _replace(val, old, new)
    elif isinstance(node, list):
        for i, val in enumerate(node):
            node[i] = new if val == old else _replace(val, old, new)
    return node


def coherent(cp, export, mutate, *, rewrite_cp=True):
    """Mutate execution_envelope.operation in a copy, then replace the old operation digest by the new canonical digest in the export (and, if asked, in a COPY of the Control Plane record)."""
    cp, export = copy.deepcopy(cp), copy.deepcopy(export)
    old = I._sha256(export["execution_envelope"]["operation"])
    mutate(export["execution_envelope"]["operation"])
    new = I._sha256(export["execution_envelope"]["operation"])
    _replace(export, old, new)
    if rewrite_cp:
        _replace(cp, old, new)
    return cp, export, old, new


def test_fixture_hashes_are_pinned():
    pinned = json.loads((FIX / "PROVENANCE.json").read_text())["sha256"]
    for name, digest in pinned.items():
        assert hashlib.sha256((FIX / name).read_bytes()).hexdigest() == digest, name


# ----------------------------------------------------------------------------------------------------------------------- positives
def test_p1_valid_strict_tenant_execution_is_accepted():
    cp, proposal, export = load(FIX)
    assert proposal["tenant_id"] == ALPHA and export["execution_envelope"]["operation"]["tenant_id"] == ALPHA
    assert run(cp, proposal, export).status == "reconstruction_complete"


def test_p_control_a_coherent_reseal_that_changes_nothing_is_accepted():
    cp, proposal, export = load(FIX)
    cp2, export2, old, new = coherent(cp, export, lambda op: None)
    assert old == new and run(cp2, proposal, export2).status == "reconstruction_complete"


@pytest.mark.parametrize("scenario", ["valid", "lost_ack", "race", "revoked"])
def test_p2_n2f_valid_historical_tenantless_executions_keep_their_behaviour(scenario):
    cp, proposal, export = load(CUR / scenario)
    assert "tenant_id" not in proposal and "tenant_id" not in export["execution_envelope"]["operation"]
    assert run(cp, proposal, export, CUR_LABEL).status == "reconstruction_complete"


# ----------------------------------------------------------------------------------------------------------------------- negatives
def test_n2a_executor_tenant_mutated_with_the_control_plane_record_unchanged_is_refused():
    cp, proposal, export = load(FIX)
    cp2, export2, _, _ = coherent(cp, export, lambda op: op.__setitem__("tenant_id", "tenant-beta"), rewrite_cp=False)
    with pytest.raises(ImportContractError):
        run(cp2, proposal, export2)


def test_n2b_coherent_foreign_tenant_rewrite_is_refused_for_the_operation_to_proposal_tenant_mismatch():
    """DECISIVE. Export digests and the Control Plane observation digest all agree on the tenant-beta operation; proposal and binding still say tenant-alpha."""
    cp, proposal, export = load(FIX)
    cp2, export2, old, new = coherent(cp, export, lambda op: op.__setitem__("tenant_id", "tenant-beta"))
    assert old != new and cp2 != cp
    with pytest.raises(ImportContractError) as exc:
        run(cp2, proposal, export2)
    assert exc.value.code == "binding_contract_mismatch", (exc.value.code, str(exc.value))
    assert "execution_envelope.operation.tenant_id" in str(exc.value), str(exc.value)
    assert "digest" not in str(exc.value), "refused for an unrelated digest reason: " + str(exc.value)


def test_n2c_tenant_missing_from_a_strict_tenant_executor_operation_is_refused():
    cp, proposal, export = load(FIX)
    cp2, export2, old, new = coherent(cp, export, lambda op: op.pop("tenant_id"))
    assert old != new
    with pytest.raises(ImportContractError) as exc:
        run(cp2, proposal, export2)
    assert exc.value.code == "binding_contract_mismatch" and "execution_envelope.operation.tenant_id" in str(exc.value), str(exc.value)


@pytest.mark.parametrize("bad", [None, "", 7, True, ["tenant-alpha"], {"id": "tenant-alpha"}], ids=["null", "empty", "int", "bool", "list", "object"])
def test_n2d_null_empty_or_invalid_typed_operation_tenant_is_refused(bad):
    cp, proposal, export = load(FIX)
    cp2, export2, _, _ = coherent(cp, export, lambda op: op.__setitem__("tenant_id", bad))
    with pytest.raises(ImportContractError) as exc:
        run(cp2, proposal, export2)
    assert exc.value.code == "binding_contract_mismatch" and "execution_envelope.operation.tenant_id" in str(exc.value), str(exc.value)


@pytest.mark.parametrize("near", ["Tenant-Alpha", "TENANT-ALPHA", " tenant-alpha", "tenant-alpha ", "tenant-alpha\n", "tenant_alpha", "tenant-alpha-2"])
def test_n2e_valid_proposal_and_binding_with_a_conflicting_or_near_miss_executor_tenant_is_refused(near):
    """Exact string equality: no case folding, trimming, aliasing."""
    cp, proposal, export = load(FIX)
    cp2, export2, _, _ = coherent(cp, export, lambda op: op.__setitem__("tenant_id", near))
    with pytest.raises(ImportContractError) as exc:
        run(cp2, proposal, export2)
    assert exc.value.code == "binding_contract_mismatch" and "execution_envelope.operation.tenant_id" in str(exc.value), str(exc.value)


def test_n2f_a_tenantless_proposal_with_a_tenant_bearing_operation_is_refused():
    """Neither-side rule: tenantless on BOTH sides is the only case where nothing is compared."""
    cp, proposal, export = load(CUR / "valid")
    cp2, export2, old, new = coherent(cp, export, lambda op: op.__setitem__("tenant_id", ALPHA))
    assert old != new
    with pytest.raises(ImportContractError) as exc:
        run(cp2, proposal, export2, CUR_LABEL)
    assert "execution_envelope.operation.tenant_id" in str(exc.value), str(exc.value)
