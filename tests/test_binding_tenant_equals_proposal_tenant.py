"""A decision binding's ``tenant_id`` must equal its proposal's ``tenant_id`` (retained negative regression for the original counterexample).

Original finding: ``import_bounded_workflow`` accepted a decision whose ``binding.tenant_id`` differed from the proposal's ``tenant_id`` (only ``decisions[0].binding.tenant_id``
changed to ``tenant-beta``, or the whitespace-padded ``tenant-alpha ``), for strict and legacy records, under the CUR and the strict-tenant labels. Cause:
``_validate_proposal_binding`` never compared ``tenant_id`` and ``_expected_effect_id`` does not hash it (Control Plane ``_effect_id`` does not either; the effect identity is NOT changed).

Fixtures are the REAL Control Plane 484fdbd2 records in ``tests/fixtures/strict_tenant_generation`` (never hand edited); only the explicit mutations below edit them, on deep copies.
Every ``match=`` pins the refusal reason. Cases marked BASE-REFUSED were already refused on the base source by the generation check (``binding.generation requires a non-empty
tenant_id``); they are retained as regressions and pin that existing reason. All other negatives fail on base (the record was accepted). Synthetic data only; builder-authored,
not independent qualification."""
import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

FIX = Path(__file__).parent / "fixtures" / "strict_tenant_generation"
CUR_FIX = Path(__file__).parent / "fixtures" / "current_generation"
NEW_CP = I.CONTROL_PLANE_STRICT_TENANT_REVISION
CUR_CP = I.CONTROL_PLANE_CUR_REVISION
LABELS = pytest.mark.parametrize("label", [CUR_CP, NEW_CP], ids=["CUR", "STRICT_TENANT_LABEL"])
KINDS = pytest.mark.parametrize("kind", ["strict", "legacy"])
STRICT_ID = "sha256:4e5844d6d53ab6f8694e9c76cb6238ec4110137dd35de73cb0b22963961ecde8"
LEGACY_ID = "sha256:f42a2866e8359b1adca34c53c91f5f56b375203b6957fd7408f70d211629452a"
EFFECT_BEARING = ("decisions", "attempts", "observations", "reconciliations")
CONFLICT = r"decisions\[0\]\.binding\.tenant_id conflicts with committed operation"
MISSING_ON_BINDING_BASE = r"decisions\[0\]\.binding\.generation requires a non-empty tenant_id on the binding"
STRIPPED = r"decisions\[0\]\.binding\.tenant_id requires a non-empty tenant_id string equal to the proposal's tenant_id"


def load(kind):
    return (json.loads((FIX / f"{kind}_control_plane_run.json").read_text(encoding="utf-8")),
            json.loads((FIX / f"{kind}_proposal.json").read_text(encoding="utf-8")))


def run(cp, proposal, label=NEW_CP, executor=None):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal),
                                   moltbot_export=copy.deepcopy(executor) if executor is not None else None, control_plane_revision=label)


def refused(cp, proposal, match, label=NEW_CP, code=None):
    with pytest.raises(ImportContractError, match=match) as exc:
        run(cp, proposal, label)
    assert exc.value.code == code
    return exc.value


def binding(cp):
    return cp["decisions"][0]["binding"]


def _swap(node, old, new):
    if isinstance(node, dict):
        return {k: _swap(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [_swap(v, old, new) for v in node]
    return new if node == old else node


def recommit(cp, proposal):
    """Make a mutated proposal consistent again (commitment, and the effect identity wherever the record repeats it), so only the tenant relationship is under test."""
    b = binding(cp)
    old, old_commitment = cp["decisions"][0]["effect_id"], b["proposal_commitment"]
    b["proposal_commitment"] = I._proposal_commitment(proposal)
    cp.update(_swap(cp, old_commitment, b["proposal_commitment"]))
    b = binding(cp)
    cp["decisions"][0]["effect_id"] = "x"
    new = I._expected_effect_id(cp["decisions"][0], b, "decisions[0]")
    cp.update(_swap(cp, old, new))
    cp["decisions"][0]["effect_id"] = new


# ---- the original counterexample: altered / padded / case-variant binding tenant is refused, strict and legacy, CUR and new label ----------------------------------
@LABELS
@KINDS
@pytest.mark.parametrize("tenant", ["tenant-beta", "tenant-alpha ", " tenant-alpha", "TENANT-ALPHA", "tenant-alpha ", "tenant‑alpha"])
def test_binding_tenant_that_differs_from_the_proposal_tenant_is_refused(kind, label, tenant):
    cp, pr = load(kind)
    assert binding(cp)["tenant_id"] == pr["tenant_id"] == "tenant-alpha"
    binding(cp)["tenant_id"] = tenant
    refused(cp, pr, CONFLICT, label)


@LABELS
@KINDS
def test_base_refused_binding_tenant_missing_is_refused(kind, label):  # BASE-REFUSED: generation check, same reason as before
    cp, pr = load(kind)
    del binding(cp)["tenant_id"]
    refused(cp, pr, MISSING_ON_BINDING_BASE, label, "binding_contract_mismatch")


@LABELS
@KINDS
def test_base_refused_binding_tenant_empty_is_refused(kind, label):  # BASE-REFUSED
    cp, pr = load(kind)
    binding(cp)["tenant_id"] = ""
    refused(cp, pr, MISSING_ON_BINDING_BASE, label, "binding_contract_mismatch")


class _S(str):
    pass


@LABELS
@KINDS
@pytest.mark.parametrize("value", [None, 5, True, ["tenant-alpha"], {"t": "tenant-alpha"}, _S("tenant-alpha")])
def test_base_refused_binding_tenant_non_string_is_refused(kind, label, value):  # BASE-REFUSED
    cp, pr = load(kind)
    binding(cp)["tenant_id"] = value
    refused(cp, pr, MISSING_ON_BINDING_BASE, label, "binding_contract_mismatch")


@LABELS
def test_legacy_binding_stripped_of_both_tenant_and_generation_while_the_proposal_has_a_tenant_is_refused(label):
    """FAILS ON BASE: the legacy 0.2 effect identity equals the tenantless one, so removing tenant_id and generation left a valid-looking tenantless binding for a tenant proposal."""
    cp, pr = load("legacy")
    del binding(cp)["tenant_id"]
    del binding(cp)["generation"]
    assert I._expected_effect_id(cp["decisions"][0], binding(cp), "decisions[0]") == LEGACY_ID == cp["decisions"][0]["effect_id"]  # the identity check alone cannot catch it
    refused(cp, pr, STRIPPED, label, "binding_contract_mismatch")


# ---- proposal side: the binding tenant present while the proposal tenant is absent / null / not the same string (proposal re-committed so only the tenant differs) ------
@LABELS
@KINDS
@pytest.mark.parametrize("proposal_tenant", ["ABSENT", None, "", 5, "tenant-alpha ", "TENANT-ALPHA", "tenant-beta"])
def test_binding_tenant_without_the_exact_proposal_tenant_is_refused(kind, label, proposal_tenant):
    cp, pr = load(kind)
    if proposal_tenant == "ABSENT":
        del pr["tenant_id"]
    else:
        pr["tenant_id"] = proposal_tenant
    recommit(cp, pr)
    refused(cp, pr, CONFLICT, label)


# ---- positives: a matching tenant passes, the effect identity is unchanged ------------------------------------------------------------------------------------------
@LABELS
@pytest.mark.parametrize("kind,expected", [("strict", STRICT_ID), ("legacy", LEGACY_ID)])
def test_matching_tenant_is_accepted_and_the_effect_identity_is_unchanged(kind, expected, label):
    cp, pr = load(kind)
    assert binding(cp)["tenant_id"] == pr["tenant_id"]
    bundle = run(cp, pr, label)
    (decision,) = [r.data for r in bundle.records if r.record_type == "runtime_decision"]
    assert decision == cp["decisions"][0] and decision["binding"]["tenant_id"] == pr["tenant_id"] == "tenant-alpha"
    assert decision["effect_id"] == expected == I._expected_effect_id(cp["decisions"][0], binding(cp), "decisions[0]")  # tenant_id is not an input to the identity
    changed = copy.deepcopy(cp)
    binding(changed)["tenant_id"] = "tenant-beta"
    assert I._expected_effect_id(changed["decisions"][0], binding(changed), "decisions[0]") == expected  # unchanged by design (CP _effect_id does not hash tenant)


@LABELS
@KINDS
def test_another_matching_tenant_value_is_accepted(kind, label):
    cp, pr = load(kind)
    pr["tenant_id"] = binding(cp)["tenant_id"] = "tenant-beta"
    recommit(cp, pr)
    bundle = run(cp, pr, label)
    assert [r.data["binding"]["tenant_id"] for r in bundle.records if r.record_type == "runtime_decision"] == ["tenant-beta"]


@LABELS
@pytest.mark.parametrize("name", ["valid", "lost_ack", "race", "revoked"])
def test_tenantless_records_on_both_sides_keep_their_existing_behaviour(name, label):
    """Neither the proposal nor the binding carries a tenant (tenantless 0.1-style CUR records): nothing is compared, nothing is invented, outcome as before."""
    cp, pr, ex = (json.loads((CUR_FIX / name / f).read_text()) for f in ("control_plane_run.json", "proposal.json", "runtime_export.json"))
    assert "tenant_id" not in pr and "tenant_id" not in cp["decisions"][0]["binding"]
    bundle = run(cp, pr, label, ex)
    assert bundle.status == "reconstruction_complete"


# ---- recovery and redelivery keep valid tenant attribution ---------------------------------------------------------------------------------------------------------
@LABELS
@KINDS
def test_recovery_and_redelivery_rows_keep_the_effect_identity_and_the_decision_keeps_its_tenant(kind, label):
    cp, pr = load(kind)
    expected = STRICT_ID if kind == "strict" else LEGACY_ID
    first, second = run(cp, pr, label), run(cp, pr, label)
    assert [(r.record_type, r.data) for r in first.records] == [(r.record_type, r.data) for r in second.records]  # redelivery is deterministic
    for record_type, count in {"control_plane_attempt_transition": 2, "effect_observation": 2, "reconciliation": 2, "runtime_decision": 1}.items():
        assert [r.data["effect_id"] for r in first.records if r.record_type == record_type] == [expected] * count
    assert [r.data["binding"]["tenant_id"] for r in first.records if r.record_type == "runtime_decision"] == [pr["tenant_id"]]
    # redelivering the decision row as a second binding is refused by the existing single-binding rule, unchanged
    redelivered = copy.deepcopy(cp)
    redelivered["decisions"].append(copy.deepcopy(redelivered["decisions"][0]))
    refused(redelivered, pr, r"single-proposal importer does not support multiple authorization bindings", label)


@LABELS
@KINDS
def test_redelivered_decision_row_with_another_tenant_is_refused(kind, label):  # retained: immutable decision_id conflict (also refused on base)
    cp, pr = load(kind)
    redelivered = copy.deepcopy(cp)
    redelivered["decisions"].append(copy.deepcopy(redelivered["decisions"][0]))
    redelivered["decisions"][1]["binding"]["tenant_id"] = "tenant-beta"
    refused(redelivered, pr, r"conflicting content under immutable decision_id", label)


@LABELS
@KINDS
@pytest.mark.parametrize("section", ["attempts", "observations", "reconciliations"])
def test_recovery_rows_carry_no_tenant_and_import_unchanged_with_a_matching_decision(kind, label, section):
    cp, pr = load(kind)
    assert all("tenant_id" not in row for row in cp[section])  # tenant attribution lives on the decision binding only; these rows are not given one
    bundle = run(cp, pr, label)
    assert any(r.source_path.startswith(f"{section}[") for r in bundle.records)
