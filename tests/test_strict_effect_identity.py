"""Replay-2 (P1 D1): the effect identity Replay recomputes is generation-aware, exactly as the Control Plane computes it.

Control Plane (cogno-us/cognous-control-plane PR #109, CP-2 head 5bff525a): ``effect_id = sha256(canonical{proposal, grant_id, grant_revision})`` for a
LEGACY (bounded-authorization-effect/0.2) or tenantless binding, and the same object plus ``tenant_generation`` for the STRICT
(bounded-authorization-effect/0.3-strict-tenant) generation. The generation is read from the persisted binding; a wrong, missing or conflicting
generation is a deterministic refusal; nothing is coerced between generations. Fixtures in tests/fixtures/strict_generation are REAL Control Plane
records (generate_from_cp.py, run against the CP-2 head, never hand edited); only the explicit mutations below edit them, on deep copies.
Synthetic data only; builder-authored, not independent qualification."""
import copy
import json
from pathlib import Path

import pytest

import agent_replay_bundle.importers as I
from agent_replay_bundle.importers import ImportContractError, _sha256, import_bounded_workflow
from agent_replay_bundle.json_equality import json_equal

D = Path(__file__).parent / "fixtures" / "strict_generation"
STRICT, LEGACY = I.TENANT_GENERATION_STRICT, I.TENANT_GENERATION_LEGACY
REV = I.CONTROL_PLANE_REVISION  # profile-neutral revision: the identity check precedes every profile-specific journal check


def load(kind):
    return (json.loads((D / f"{kind}_control_plane_run.json").read_text(encoding="utf-8")),
            json.loads((D / f"{kind}_proposal.json").read_text(encoding="utf-8")))


def run(cp, proposal):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=REV)


def refused_identity(cp, proposal, text="has invalid effect identity", code=None):
    with pytest.raises(ImportContractError) as exc:
        run(cp, proposal)
    assert text in str(exc.value)
    assert exc.value.code == code
    return exc.value


def dec(cp):
    return cp["decisions"][0]


def identity(binding, *, strict):
    o = {"proposal": binding["proposal_commitment"], "grant_id": binding["grant_id"], "grant_revision": binding["grant_revision"]}
    if strict:
        o["tenant_generation"] = STRICT
    return _sha256(o)


def effect_checked(report):
    return [c for c in report.commitments if c.label == "effect_id" and c.verification_status == "checked_match"]


# ---- the shared vector (also written to /tmp/claude-0/p1/impl/identity-vectors/ for the Verifier-2 lane) --------------------------
def test_vectors_cp_effect_id_equals_replay_expected_effect_id():
    vectors = json.loads((D / "vectors.json").read_text(encoding="utf-8"))
    for kind, gen in (("strict", STRICT), ("legacy", LEGACY)):
        v = vectors[kind]
        cp, _ = load(kind)
        b = dec(cp)["binding"]
        assert (v["proposal"], v["grant_id"], v["grant_revision"], v["generation"]) == (b["proposal_commitment"], b["grant_id"], b["grant_revision"], gen)
        assert v["control_plane_effect_id"] == v["expected_effect_id"] == dec(cp)["effect_id"]
        assert I._expected_effect_id(dec(cp), b, "decisions[0]") == v["expected_effect_id"] == identity(b, strict=(kind == "strict"))
    assert vectors["strict"]["expected_effect_id"] != vectors["legacy"]["expected_effect_id"]


# ---- 1 / 5 positives ----------------------------------------------------------------------------------------------------------
def test_1_strict_positive_effect_identity():
    cp, pr = load("strict")
    assert dec(cp)["binding"]["generation"] == STRICT
    report = run(cp, pr)
    assert len(effect_checked(report)) == 1 and effect_checked(report)[0].value == dec(cp)["effect_id"]


def test_5_legacy_02_positive():
    cp, pr = load("legacy")
    assert dec(cp)["binding"]["generation"] == LEGACY
    report = run(cp, pr)
    assert len(effect_checked(report)) == 1 and effect_checked(report)[0].value == dec(cp)["effect_id"]


# ---- 2 tampered / wrong generation marker ---------------------------------------------------------------------------------------
class _S(str):
    pass


@pytest.mark.parametrize("bad", [STRICT + " ", " " + STRICT, "bounded-authorization-effect/0.3", "STRICT", "", "bounded-authorization-effect/0.2 ",
                                 None, 1, True, [STRICT], {"g": STRICT}, _S(STRICT), _S(LEGACY)])
@pytest.mark.parametrize("kind", ["strict", "legacy"])
def test_2_wrong_or_tampered_generation_marker_is_refused(kind, bad):
    cp, pr = load(kind)
    dec(cp)["binding"]["generation"] = bad
    refused_identity(cp, pr, "not a supported tenant-binding generation", "binding_contract_mismatch")


# ---- 3 missing generation -----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["strict", "legacy"])
def test_3_missing_generation_on_a_tenant_aware_binding_is_refused(kind):
    cp, pr = load(kind)
    del dec(cp)["binding"]["generation"]
    refused_identity(cp, pr, "binding.generation is required", "binding_contract_mismatch")


def test_generation_without_tenant_is_refused():
    for kind in ("strict", "legacy"):
        cp, pr = load(kind)
        del dec(cp)["binding"]["tenant_id"]
        refused_identity(cp, pr, "requires a non-empty tenant_id", "binding_contract_mismatch")
    cp, pr = load("strict")
    dec(cp)["binding"]["tenant_id"] = ""
    refused_identity(cp, pr, "requires a non-empty tenant_id", "binding_contract_mismatch")


@pytest.mark.parametrize("member", ["tenant_generation", "generation"])
def test_conflicting_decision_level_generation_is_refused(member):
    cp, pr = load("strict")
    dec(cp)[member] = LEGACY
    refused_identity(cp, pr, f"decisions[0].{member} conflicts with binding.generation", "binding_contract_mismatch")
    cp, pr = load("legacy")
    dec(cp)[member] = STRICT
    refused_identity(cp, pr, f"decisions[0].{member} conflicts with binding.generation", "binding_contract_mismatch")


# ---- 4 strict record whose effect_id was computed with the legacy algorithm ------------------------------------------------------
def test_4_strict_record_with_legacy_algorithm_effect_id_is_refused():
    cp, pr = load("strict")
    b = dec(cp)["binding"]
    dec(cp)["effect_id"] = identity(b, strict=False)
    assert dec(cp)["effect_id"] != identity(b, strict=True)
    refused_identity(cp, pr)


# ---- 6 legacy record falsely marked strict / 7 strict record forced into legacy ------------------------------------------------------
def test_6_legacy_record_falsely_marked_strict_is_refused():
    cp, pr = load("legacy")
    dec(cp)["binding"]["generation"] = STRICT
    refused_identity(cp, pr)


def test_7_strict_record_forced_into_legacy_semantics_is_refused():
    cp, pr = load("strict")
    dec(cp)["binding"]["generation"] = LEGACY
    refused_identity(cp, pr)
    # the strict identity is not accepted under a stripped or foreign marker either
    cp, pr = load("strict")
    del dec(cp)["binding"]["generation"]
    refused_identity(cp, pr, "binding.generation is required", "binding_contract_mismatch")


# ---- 8 / 9 persisted reload keeps its generation ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("kind,gen", [("strict", STRICT), ("legacy", LEGACY)])
def test_8_9_persisted_record_reload_keeps_its_generation(tmp_path, kind, gen):
    cp, pr = load(kind)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(cp), encoding="utf-8")
    reloaded = json.loads(path.read_bytes())
    assert dec(reloaded)["binding"]["generation"] == gen
    assert I._binding_generation(dec(reloaded), dec(reloaded)["binding"], "d") == gen
    assert len(effect_checked(run(reloaded, pr))) == 1
    # a reload never infers a generation from the other one: flipping the stored marker after the reload is refused
    flipped = copy.deepcopy(reloaded)
    dec(flipped)["binding"]["generation"] = LEGACY if gen == STRICT else STRICT
    refused_identity(flipped, pr)


def test_tenantless_binding_keeps_the_historical_identity():
    p = Path(__file__).parent / "fixtures" / "programme2_paired" / "adapter-default"
    cp = json.loads((p / "control_plane_run.json").read_text(encoding="utf-8"))
    b = dec(cp)["binding"]
    assert "generation" not in b and "tenant_id" not in b
    assert dec(cp)["effect_id"] == identity(b, strict=False)
    assert I._binding_generation(dec(cp), b, "d") is None
    dec(cp)["generation"] = STRICT
    with pytest.raises(ImportContractError) as exc:
        import_bounded_workflow(cp, proposal=json.loads((p / "proposal.json").read_text(encoding="utf-8")), control_plane_revision=I.CONTROL_PLANE_P2_REVISION)
    assert exc.value.code == "binding_contract_mismatch"


# ---- 10 Replay-1 typed JSON-semantic equality intact -----------------------------------------------------------------------------------
def test_10_typed_json_semantic_equality_still_applies_to_strict_records():
    assert not json_equal(True, 1) and not json_equal(False, 0.0) and json_equal(50, 50.0) and json_equal(0, -0.0)
    cp, pr = load("strict")
    assert pr["effects"] == 1 and not isinstance(pr["effects"], bool)
    dec(cp)["binding"]["effects"] = True  # Python == would accept True for 1
    with pytest.raises(ImportContractError) as exc:
        run(cp, pr)
    assert "binding.effects" in str(exc.value) and "has invalid effect identity" not in str(exc.value)
    cp, pr = load("strict")
    pr["effects"] = True
    with pytest.raises(ImportContractError):
        run(cp, pr)


# ---- 11 no claim B / 12 registry_authenticated semantics unchanged -----------------------------------------------------------------
@pytest.mark.parametrize("kind", ["strict", "legacy"])
def test_11_12_no_claim_b_and_registry_authenticated_unchanged(kind):
    report = run(*load(kind))
    text = json.dumps(report.model_dump(mode="json") if hasattr(report, "model_dump") else report.__dict__, default=str)
    assert '"registry_authenticated": true' not in text.lower()
    assert "claim_b" not in text and "decision_authentic" not in text and "registry_origin_verified" not in text
    assert "registry_authenticated" not in text or '"registry_authenticated": false' in text


def test_12_registry_authenticated_selection_semantics_unchanged():
    from tests import test_registry_authenticated_selection_f4_governed as F
    trust = F._trust()
    md = F._import(trust=trust).metadata
    assert md["registry_authenticated"] is False and md["registry_origin"] == "registry_origin_unverified"
    assert md["control_plane_decision_authenticated"] is False
    assert [k for k in md if k.startswith(("claim_b", "decision_authentic", "registry_origin_verified"))] == []
