"""STRICT-TENANT generation: Control Plane 484fdbd2 (bounded-authorization-effect/0.3-strict-tenant), added BESIDE the existing generations.

OCS clean contract reset, Option 2: Replay accepts ONE new exact Control Plane label, ``484fdbd297235dd24148ddb0703f2055a31eabff``, with its own generation identifier
``control-plane-strict-tenant-stack@484fdbd2``, paired with the unchanged CUR runtime f7a55e2a and manifest fa170815. No existing label is repointed, renamed or removed (their
sets are byte-unchanged and still asserted by their own tests). Strict tenant-aware effect identity, source provenance, authority, refusal and recovery semantics are those the
importer already enforces; this file proves they hold under the new label and that nothing is silently substituted.

The records in ``tests/fixtures/strict_tenant_generation`` are REAL Control Plane 484fdbd2 records (generate_from_cp.py, never hand edited); only the explicit mutations below
edit them, on deep copies. The shared identity vectors are strict sha256:4e5844d6...ecde8 and legacy sha256:f42a2866...9452a. Synthetic data only. This is a PROVISIONAL
DEVELOPMENT PIN, UNQUALIFIED, builder-authored (not independent qualification), non-authorizing; the Constitution is assigned at pin 1c2e920f, adoption not recorded.
"""
import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.effective_configuration import REGISTRY_GOVERNED_PROFILE
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow
from agent_replay_bundle.registry_evidence import REGISTRY_AUTHENTICATED_SELECTION_F4_PROFILE, REGISTRY_AUTHENTICATED_SELECTION_PROFILE

FIX = Path(__file__).parent / "fixtures" / "strict_tenant_generation"
CUR_FIX = Path(__file__).parent / "fixtures" / "current_generation"
NEW_CP = "484fdbd297235dd24148ddb0703f2055a31eabff"
NEW_PROFILE = "control-plane-strict-tenant-stack@484fdbd2"
CUR_CP, CUR_RT, CUR_MANIFEST = I.CONTROL_PLANE_CUR_REVISION, I.MOLTBOT_CUR_REVISION, I.MANIFEST_CUR_REVISION
P2_CP, P2_RT = I.CONTROL_PLANE_P2_REVISION, I.MOLTBOT_P2_REVISION
STRICT, LEGACY = I.TENANT_GENERATION_STRICT, I.TENANT_GENERATION_LEGACY
STRICT_ID = "sha256:4e5844d6d53ab6f8694e9c76cb6238ec4110137dd35de73cb0b22963961ecde8"
LEGACY_ID = "sha256:f42a2866e8359b1adca34c53c91f5f56b375203b6957fd7408f70d211629452a"
LINEAGE_OR_IDENTITY = "has invalid effect identity|journal decision/effect lineage mismatch"  # whichever refusal fires first; both are fail-closed
EFFECT_BEARING = ("decisions", "attempts", "observations", "reconciliations")
OLD_LABELS = [I.CONTROL_PLANE_REVISION, *I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS]


def load(kind):
    return (json.loads((FIX / f"{kind}_control_plane_run.json").read_text(encoding="utf-8")),
            json.loads((FIX / f"{kind}_proposal.json").read_text(encoding="utf-8")))


def load_cur(name="valid"):
    return tuple(json.loads((CUR_FIX / name / f).read_text()) for f in ("control_plane_run.json", "proposal.json", "runtime_export.json"))


def run(cp, proposal, executor=None, revision=NEW_CP, **kw):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal),
                                   moltbot_export=copy.deepcopy(executor) if executor is not None else None, control_plane_revision=revision, **kw)


def refused(cp, proposal, executor=None, revision=NEW_CP, match=None, **kw):
    with pytest.raises(ImportContractError, match=match) as exc:
        run(cp, proposal, executor, revision, **kw)
    return exc.value


def effect_ids(bundle):
    return [r.data["effect_id"] for r in bundle.records if isinstance(r.data, dict) and "effect_id" in r.data and r.record_type != "resolution_check_event"]


# ------------------------------------------------------------------------------------------------ the exact pin, registered additively
def test_the_strict_tenant_pin_is_exactly_this_and_has_its_own_generation_identifier():
    assert I.CONTROL_PLANE_STRICT_TENANT_REVISION == NEW_CP and len(NEW_CP) == 40
    assert I.BOUNDED_STRICT_TENANT_PROFILE == NEW_PROFILE
    assert I.STRICT_TENANT_CP_REVISIONS == frozenset({NEW_CP})
    other_profiles = {I.BOUNDED_PROFILE, I.BOUNDED_V2_PROFILE, I.BOUNDED_V2_PERSISTENCE_PROFILE, I.BOUNDED_MERGED_PROFILE, I.BOUNDED_REFUSAL_PROFILE,
                      I.BOUNDED_RUNTIME_AUTHORITY_PROFILE, I.BOUNDED_SECURITY_PROFILE, I.BOUNDED_F5B_PROFILE, I.BOUNDED_P4_PROFILE, I.BOUNDED_P2_PROFILE,
                      I.BOUNDED_CUR_PROFILE, I.BOUNDED_CUR_REGISTRY_GOVERNED_PROFILE, I.BOUNDED_CUR_REGISTRY_AUTHENTICATED_PROFILE}
    assert NEW_PROFILE not in other_profiles and len(other_profiles) == 13  # unique; no existing profile string reused or removed


def test_no_existing_generation_set_was_changed_and_the_old_labels_are_still_there():
    assert NEW_CP not in OLD_LABELS and NEW_CP not in I.PROGRAMME2_CP_REVISIONS and NEW_CP not in I.SECURITY_RUNTIME_CP_REVISIONS
    assert len(set(OLD_LABELS)) == 11  # the default label plus the ten repaired-generation labels, all untouched
    assert I.PROGRAMME2_CP_REVISIONS == frozenset({P2_CP, CUR_CP})
    assert I.CONTROL_PLANE_CUR_REVISION == "b19c47ddd020409d24e52e70b11359c46265edbb"
    assert I.MOLTBOT_CUR_PROFILE in I.STRICT_ACK_PROFILES


@pytest.mark.parametrize("label", OLD_LABELS)
def test_every_existing_label_is_still_accepted_not_repointed(label):
    cp, proposal = load("strict")
    try:
        bundle = run(cp, proposal, None, label)
    except ImportContractError as exc:  # shape-specific refusals of older generations are theirs, never "unsupported Control Plane revision"
        assert "unsupported Control Plane revision" not in str(exc)
    else:
        assert bundle.metadata["control_plane_revision"] == label and bundle.import_reports[0].adapter_profile != NEW_PROFILE


# ------------------------------------------------------------------------------------------------ the correct generation is accepted
@pytest.mark.parametrize("kind", ["strict", "legacy"])
def test_real_strict_tenant_control_plane_record_is_accepted_under_the_new_label(kind):
    cp, proposal = load(kind)
    bundle = run(cp, proposal)
    assert bundle.import_reports[0].adapter_profile == NEW_PROFILE and bundle.import_reports[0].source_revision == NEW_CP
    assert {r.producer_profile_id for r in bundle.records} == {NEW_PROFILE}
    (decision,) = [r.data for r in bundle.records if r.record_type == "runtime_decision"]
    assert decision == cp["decisions"][0]
    meta = bundle.metadata
    assert (meta["control_plane_revision"], meta["moltbot_safe_revision"], meta["manifest_revision"]) == (NEW_CP, None, CUR_MANIFEST)
    assert meta["executor_failure_reference_verification"] == "source_asserted_not_independently_verified"
    assert bundle.status == "reconstruction_partial"  # no executor evidence: partial by design, as under CUR


def test_new_label_accepts_the_unchanged_cur_runtime_and_records_the_pairing_exactly():
    cp, proposal, executor = load_cur()
    assert executor["repository"]["revision"] == CUR_RT
    bundle = run(cp, proposal, executor)
    assert bundle.status == "reconstruction_complete" and [r.complete for r in bundle.import_reports] == [True]
    assert bundle.import_reports[0].adapter_profile == NEW_PROFILE
    meta = bundle.metadata
    assert (meta["control_plane_revision"], meta["moltbot_safe_revision"], meta["manifest_revision"]) == (NEW_CP, CUR_RT, CUR_MANIFEST)
    assert meta["moltbot_producer_contract"]["profile_id"] == I.MOLTBOT_CUR_PROFILE
    assert meta["moltbot_producer_contract"]["compatible_control_plane_revisions"] == [NEW_CP]
    # the CUR output is unchanged by this generation
    cur = run(cp, proposal, executor, CUR_CP)
    assert cur.metadata["moltbot_producer_contract"]["compatible_control_plane_revisions"] == [CUR_CP] and cur.import_reports[0].adapter_profile == I.BOUNDED_CUR_PROFILE


# ------------------------------------------------------------------------------------------------ wrong / unknown generation is refused
@pytest.mark.parametrize("label", [
    "484fdbd2", NEW_CP[:12], NEW_CP.upper(), NEW_CP + "0", " " + NEW_CP, NEW_CP + "\n", "0" * 40, "f" * 40, "", "latest", "484fdbd*",
    "0a41faa9" + "0" * 32, "7a4bcd40" + NEW_CP[8:], NEW_CP[:39] + "0",
])
def test_an_unknown_or_non_exact_label_is_refused(label):
    cp, proposal = load("strict")
    refused(cp, proposal, None, label, "unsupported Control Plane revision")


def test_the_lock_label_0a41faa9_is_still_not_accepted():
    cp, proposal = load("strict")
    refused(cp, proposal, None, "0a41faa9ac05ab7a4f8d17a1b3e4e2bf36e99d50", "unsupported Control Plane revision")


def test_the_new_label_is_refused_with_a_historical_runtime_export():
    cp, proposal, executor = load_cur()
    historical = copy.deepcopy(executor)
    historical["repository"]["revision"] = P2_RT
    historical["provenance"]["source_asserted"]["repository_revision"] = P2_RT
    refused(cp, proposal, historical, NEW_CP, "unsupported executor/Control Plane revision combination")
    refused(cp, proposal, executor, P2_CP, "unsupported executor/Control Plane revision combination")  # historical CP + current runtime, unchanged
    refused(cp, proposal, executor, I.CONTROL_PLANE_P4_REVISION, "unsupported executor/Control Plane revision combination")


@pytest.mark.parametrize("profile", [REGISTRY_GOVERNED_PROFILE, REGISTRY_AUTHENTICATED_SELECTION_PROFILE, REGISTRY_AUTHENTICATED_SELECTION_F4_PROFILE, "anything"])
def test_registry_profile_selectors_stay_current_only_and_are_refused_for_the_new_label(profile):
    cp, proposal = load("strict")
    refused(cp, proposal, None, NEW_CP, "unsupported Control Plane profile selector", control_plane_profile=profile)


# ------------------------------------------------------------------------------------------------ strict identity equals the Control Plane's computation
@pytest.mark.parametrize("kind,generation,expected", [("strict", STRICT, STRICT_ID), ("legacy", LEGACY, LEGACY_ID)])
def test_effect_identity_equals_the_control_plane_computation_and_the_shared_vector(kind, generation, expected):
    cp, proposal = load(kind)
    vectors = json.loads((FIX / "vectors.json").read_text(encoding="utf-8"))[kind]
    b = cp["decisions"][0]["binding"]
    assert b["generation"] == generation and vectors["generation"] == generation and b["tenant_id"] == "tenant-alpha"
    assert cp["decisions"][0]["effect_id"] == vectors["effect_id"] == expected  # as written by the Control Plane's own _effect_id
    assert I._expected_effect_id(cp["decisions"][0], b, "decision") == expected  # Replay's single recompute site agrees
    bundle = run(cp, proposal)
    assert [c.verification_status for c in bundle.commitments if c.label == "effect_id"] == ["checked_match"]
    assert set(effect_ids(bundle)) == {expected} and len(effect_ids(bundle)) == 7


def test_strict_and_legacy_identities_differ_by_exactly_the_generation_marker():
    cp, _ = load("strict")
    b = cp["decisions"][0]["binding"]
    base = {"proposal": b["proposal_commitment"], "grant_id": b["grant_id"], "grant_revision": b["grant_revision"]}
    assert I._sha256(base) == LEGACY_ID != STRICT_ID == I._sha256({**base, "tenant_generation": STRICT})


# ------------------------------------------------------------------------------------------------ no silent substitution, in either direction
def test_a_legacy_identity_is_not_substituted_for_a_strict_record():
    cp, proposal = load("strict")
    mutated = copy.deepcopy(cp)
    mutated["decisions"][0]["effect_id"] = LEGACY_ID
    refused(mutated, proposal, None, NEW_CP, LINEAGE_OR_IDENTITY)


def test_a_strict_identity_is_not_substituted_for_a_legacy_record():
    cp, proposal = load("legacy")
    mutated = copy.deepcopy(cp)
    mutated["decisions"][0]["effect_id"] = STRICT_ID
    refused(mutated, proposal, None, NEW_CP, LINEAGE_OR_IDENTITY)


def test_a_strict_record_downgraded_to_the_legacy_generation_marker_is_refused():
    cp, proposal = load("strict")
    mutated = copy.deepcopy(cp)
    mutated["decisions"][0]["binding"]["generation"] = LEGACY  # marker flipped, identity left strict
    refused(mutated, proposal, None, NEW_CP, LINEAGE_OR_IDENTITY)


def test_a_strict_record_with_the_generation_marker_removed_is_refused():
    cp, proposal = load("strict")
    mutated = copy.deepcopy(cp)
    del mutated["decisions"][0]["binding"]["generation"]
    refused(mutated, proposal, None, NEW_CP)


def test_an_unknown_generation_marker_is_refused():
    cp, proposal = load("strict")
    mutated = copy.deepcopy(cp)
    mutated["decisions"][0]["binding"]["generation"] = "bounded-authorization-effect/0.4-unknown"
    refused(mutated, proposal, None, NEW_CP)


# ------------------------------------------------------------------------------------------------ recovery and redelivery retain source identity
@pytest.mark.parametrize("kind,expected", [("strict", STRICT_ID), ("legacy", LEGACY_ID)])
def test_every_attempt_observation_and_reconciliation_retains_the_source_identity(kind, expected):
    cp, proposal = load(kind)
    for section in EFFECT_BEARING:
        assert cp[section] and {x["effect_id"] for x in cp[section]} == {expected}
    bundle = run(cp, proposal)
    kinds = {"control_plane_attempt_transition": 2, "effect_observation": 2, "reconciliation": 2, "runtime_decision": 1}
    for record_type, count in kinds.items():
        got = [r.data["effect_id"] for r in bundle.records if r.record_type == record_type]
        assert got == [expected] * count


def test_redelivery_of_the_same_record_is_deterministic_and_keeps_identity():
    cp, proposal = load("strict")
    first, second = run(cp, proposal), run(cp, proposal)
    assert [(r.record_type, r.data) for r in first.records] == [(r.record_type, r.data) for r in second.records]
    assert effect_ids(first) == effect_ids(second) and set(effect_ids(first)) == {STRICT_ID}


@pytest.mark.parametrize("section", ["attempts", "observations", "reconciliations"])
def test_a_recovery_or_redelivered_row_that_swaps_in_the_legacy_identity_is_refused(section):
    cp, proposal = load("strict")
    mutated = copy.deepcopy(cp)
    mutated[section][-1]["effect_id"] = LEGACY_ID  # a later (recovery / redelivered) row drops the strict marker
    with pytest.raises(ImportContractError):
        run(mutated, proposal)


def test_the_recovered_lost_acknowledgement_scenario_is_accepted_under_the_new_label_with_its_identity_retained():
    cp, proposal, executor = load_cur("lost_ack")
    ids = {x["effect_id"] for s in EFFECT_BEARING for x in cp[s]}
    assert len(ids) == 1
    bundle = run(cp, proposal, executor)
    assert bundle.status == "reconstruction_complete" and set(effect_ids(bundle)) == ids
    assert bundle.metadata["control_plane_revision"] == NEW_CP
