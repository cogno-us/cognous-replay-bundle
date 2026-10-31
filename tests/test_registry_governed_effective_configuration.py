"""Registry-governed effective-configuration profile (``registry-governed-effective-configuration/0.1``), added beside the current generation.

The positive cases are REAL run records written by the Control Plane b19c47dd's own Registry-governed workflow (Registry r08-v8 code, synthetic Ed25519 material;
``tests/fixtures/registry_governed_effective_configuration``, provenance and capture script alongside). Every digest the profile recomputes is compared with the digest the
real Control Plane recorded (literal vectors below), so the re-implementation of the producing contract is cross-checked, not self-validated.

What this proves: the member is admitted ONLY under the explicit selector, only on the current-generation revision, only with the exact member shape/version/digest and the
Control Plane family table; missing, forged, malformed, unsupported-version and conflicting members are refused; the plain current profile, P2, P4 and every earlier label
still refuse the member. What it does NOT prove (asserted in the last section, never hidden): that the configuration is the one in force, that the Registry material was
genuine or at which Registry revision, or that anything is qualified. A self-consistent forgery (members edited and the digest recomputed) is NOT detectable from the record.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import effective_configuration as EC
from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import import_bounded_workflow

HERE = Path(__file__).parent / "fixtures"
FIX = HERE / "registry_governed_effective_configuration"
PLAIN = HERE / "current_generation"
CUR_CP = "b19c47ddd020409d24e52e70b11359c46265edbb"
P2_CP = "7a4bcd40b3b49e61ff3c294dcca53b52f460b22c"
SELECTOR = "registry-governed-effective-configuration/0.1"
GOVERNED_PROFILE = "control-plane-current-stack-registry-governed-effective-configuration-0.1@b19c47dd"
VERSION = "effective-configuration-binding/0.1"
DOMAIN = "cognous.control-plane.effective-configuration-binding"
# Digests recorded by the real Control Plane b19c47dd (the first is also the digest of the independent S0 probe record, captured in a separate process).
CP_DIGESTS = {"governed_executed": "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7",
              "governed_binding_changed": "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7",
              "governed_decided_only": "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7",
              "governed_age_only": "sha256:9b83d2665fd1a0e3843385408c362c2f49863651c6d7406ee0747e3e39954c42"}
BASE_MEMBERS = {"profile", "approval_commitment", "required_inputs_digest", "catalogue_digest", "expected_effective_grant_digest", "effective_grant_derivation_version"}
SCENARIOS = sorted(CP_DIGESTS)
PLAIN_SCENARIOS = ["valid", "lost_ack", "revoked", "unreadable", "purpose_closed", "purpose_reopened", "tampered_evidence", "input_dropped", "race"]
HISTORICAL_LABELS = [P2_CP, I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_F5B_REVISION, I.CONTROL_PLANE_SECURITY_REVISION]


def load(name="governed_executed"):
    return tuple(json.loads((FIX / name / f).read_text()) for f in ("control_plane_run.json", "proposal.json"))


def member(cp):
    return cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]


def run(cp, proposal, *, selector=SELECTOR, revision=CUR_CP, export=None):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=export, control_plane_revision=revision,
                                   control_plane_profile=selector)


def refused(cp, proposal, match=None, code=None, **kw):
    with pytest.raises(ImportContractError, match=match) as caught:
        run(cp, proposal, **kw)
    if code is not None:
        assert caught.value.code == code
    return caught.value


def reseal(cp, mutate):
    """Edit the members with ``mutate`` and recompute the digest independently of the code under test, so ONLY the edit (not a digest mismatch) is what is judged."""
    cp = copy.deepcopy(cp)
    ec = member(cp)
    mutate(ec["members"])
    body = {"domain": DOMAIN, "version": ec["version"], **ec["members"]}
    ec["digest"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return cp


# ------------------------------------------------------------------------------------------------ pins and the selector
def test_the_selector_and_profile_constants_are_exactly_these_and_the_global_sets_are_not_broadened():
    assert I.REGISTRY_GOVERNED_PROFILE == EC.REGISTRY_GOVERNED_PROFILE == SELECTOR
    assert I.BOUNDED_CUR_REGISTRY_GOVERNED_PROFILE == GOVERNED_PROFILE
    assert (EC.VERSION, EC.DOMAIN, EC.KEY) == (VERSION, DOMAIN, "effective_configuration")
    # no new revision anywhere; the member set of the plain profiles is untouched (no module-level 'accepted members' set exists to extend)
    assert I.PROGRAMME2_CP_REVISIONS == frozenset({P2_CP, CUR_CP})
    assert I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS.count(CUR_CP) == 1 and I.CONTROL_PLANE_CUR_REVISION == CUR_CP
    assert (I.BOUNDED_CUR_PROFILE, I.BOUNDED_P2_PROFILE) == ("control-plane-current-stack@b19c47dd", "control-plane-programme2-profiles@7a4bcd40")
    assert I.BOUNDED_CUR_REGISTRY_GOVERNED_PROFILE not in {I.BOUNDED_CUR_PROFILE, I.BOUNDED_P2_PROFILE, I.BOUNDED_P4_PROFILE, I.BOUNDED_F5B_PROFILE, I.BOUNDED_SECURITY_PROFILE}
    assert I.BOUNDED_CUR_REGISTRY_GOVERNED_PROFILE in I.SECURITY_RUNTIME_BOUNDED_PROFILES


def test_the_family_table_is_the_control_plane_b19c47dd_table():
    assert EC.FAMILY_ORDER == ("f4_ages", "class_age", "class_unreadable", "class_revocation_assurance", "class_irreversible", "anchor_deadline",
                               "observation_max_age", "observation_clock_tolerance", "terminal_revocation")
    assert EC.FAMILY_TABLE == {
        "f4_ages": ("f4-control-plane-age-bounds", "r08-v2"), "class_age": ("f5-action-class-age-bounds", "r08-v2"),
        "class_unreadable": ("f5-action-class-unreadable-policy", "r08-v5"), "class_revocation_assurance": ("f5-action-class-revocation-assurance-policy", "r08-v6"),
        "class_irreversible": ("f5-action-class-irreversibility-policy", "r08-v7"), "anchor_deadline": ("f5-anchor-deadline-to-inputs-policy", "r08-v8"),
        "observation_max_age": ("f5-observation-max-age-policy", "r08-v8"), "observation_clock_tolerance": ("f5-observation-clock-tolerance-policy", "r08-v8"),
        "terminal_revocation": ("f5-terminal-revocation-enablement-policy", "r08-v6")}
    assert EC.SCHEMA_REVISIONS == {"class_irreversible": 1, "anchor_deadline": 1, "observation_max_age": 1, "observation_clock_tolerance": 1}
    assert set(EC.FAMILY_ORDER) == set(EC.FAMILY_TABLE)
    assert EC.SCALAR_MAX == 2147483647
    assert (EC.RECORD_FIELDS, EC.MEMBER_FIELDS) == (("version", "digest", "members"),
                                                   ("scope", "host_profile_digest", "effective_profile_digest", "f4_scalars", "other_scalars", "observation_policy", "families"))
    assert EC.SCOPE_FIELDS == ("consumer_id", "tenant_id", "action_id", "institution_id", "authority_domain")
    assert (EC.F4_FIELDS, EC.OTHER_FIELDS, EC.OBSERVATION_FIELDS) == (("status_max_age_seconds", "approval_max_age_seconds"),
        ("clock_tolerance_seconds", "identity_max_age_seconds", "mandate_max_age_seconds"), ("max_age_seconds", "clock_tolerance_seconds"))
    assert EC.FAMILY_FIELDS == ("slot", "family_id", "contract_version", "family_schema_revision", "effective_policy_digest")


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_recomputed_digest_equals_the_digest_the_real_control_plane_recorded(name):
    cp, _ = load(name)
    ec = member(cp)
    assert ec["digest"] == CP_DIGESTS[name] and ec["version"] == VERSION
    assert EC.digest_of(ec["version"], ec["members"]) == CP_DIGESTS[name]
    assert EC.record_defect(ec) is None


@pytest.mark.parametrize("selector", ["", "registry-governed-effective-configuration", "registry-governed-effective-configuration/0.2", "registry-governed-effective-configuration/0.1 ",
                                      " registry-governed-effective-configuration/0.1", "Registry-Governed-Effective-Configuration/0.1", "REGISTRY-GOVERNED-EFFECTIVE-CONFIGURATION/0.1",
                                      "registry-governed-effective-configuration/0.1\n", "registry-governed-effective-configuration/*", "registry-governed-*", "latest",
                                      "registry-governed", "control-plane-current-stack-registry-governed-effective-configuration-0.1@b19c47dd", "effective-configuration-binding/0.1",
                                      True, 1, b"registry-governed-effective-configuration/0.1", ["registry-governed-effective-configuration/0.1"], {"profile": SELECTOR}])
def test_any_selector_other_than_the_exact_string_is_refused(selector):
    cp, proposal = load()
    refused(cp, proposal, "unsupported Control Plane profile selector", selector=selector)


@pytest.mark.parametrize("revision", [P2_CP, I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_F5B_REVISION, I.CONTROL_PLANE_SECURITY_REVISION, I.CONTROL_PLANE_RUNTIME_AUTHORITY_REVISION,
                                      I.CONTROL_PLANE_REVISION, CUR_CP[:8], "latest"])
def test_the_exact_selector_with_any_revision_but_the_current_one_is_refused(revision):
    cp, proposal = load()
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector|unsupported Control Plane revision"):
        run(cp, proposal, revision=revision)


# ------------------------------------------------------------------------------------------------ positive: real records, content checked
@pytest.mark.parametrize("name", SCENARIOS)
def test_a_real_registry_governed_record_is_accepted_under_the_explicit_profile_and_its_content_retained(name):
    cp, proposal = load(name)
    bundle = run(cp, proposal)
    assert bundle.status == "reconstruction_partial"  # no Runtime export: partial by design, as for the plain current profile
    (report,) = bundle.import_reports
    assert report.adapter_profile == GOVERNED_PROFILE and report.source_revision == CUR_CP
    assert {r.producer_profile_id for r in bundle.records if r.record_type in {"runtime_decision", "runtime_proposal"}} == {GOVERNED_PROFILE}
    (decision,) = [r.data for r in bundle.records if r.record_type == "runtime_decision"]
    assert decision == cp["decisions"][0]
    assert decision["binding"]["runtime_authority"]["effective_configuration"] == member(cp)  # retained verbatim, digest and members
    assert set(decision["binding"]["runtime_authority"]) == BASE_MEMBERS | {"effective_configuration"}
    assert decision["reason_vocabulary_version"] == "runtime-authority-reasons/0.1" and decision["result"] == "authorized"
    assert [r.data for r in bundle.records if r.record_type == "runtime_proposal"] == [proposal]
    assert len([r for r in bundle.records if r.record_type == "control_plane_attempt_transition"]) == len(cp["attempts"])
    assert [r.data["reasons"] for r in bundle.records if r.record_type == "effect_time_refusal"] == [x["reasons"] for x in cp["refusals"]]
    meta = bundle.metadata
    assert meta["control_plane_revision"] == CUR_CP and meta["control_plane_profile"] == SELECTOR
    assert meta["effective_configuration_verification"] == "internal_consistency_only_registry_source_revision_unverified"
    assert meta["manifest_revision"] == I.MANIFEST_CUR_REVISION


def test_the_executed_run_has_an_acknowledged_attempt_and_the_binding_changed_run_has_a_refusal_and_no_attempt():
    cp, proposal = load("governed_executed")
    assert [a["status"] for a in cp["attempts"]] == ["attempted", "acknowledged"] and cp["refusals"] == []
    run(cp, proposal)
    cp, proposal = load("governed_binding_changed")
    # The record holds the decision-time configuration and the Control Plane's own refusal; the configuration in force at execute is not carried (see the last section).
    assert cp["attempts"] == [] and [x["reasons"] for x in cp["refusals"]] == [["authorization_binding_changed"]] and "effective_configuration" not in json.dumps(cp["refusals"])
    bundle = run(cp, proposal)
    assert [r.data["reasons"] for r in bundle.records if r.record_type == "effect_time_refusal"] == [["authorization_binding_changed"]]


def test_the_two_configurations_of_the_fixtures_are_genuinely_different_and_both_pass():
    a, _ = load("governed_executed")
    b, _ = load("governed_age_only")
    assert member(a)["digest"] != member(b)["digest"]
    assert [r["slot"] for r in member(a)["members"]["families"]] != [r["slot"] for r in member(b)["members"]["families"]]


# ------------------------------------------------------------------------------------------------ preserved refusal: plain and historical profiles
@pytest.mark.parametrize("name", SCENARIOS)
def test_the_plain_current_profile_still_refuses_effective_configuration(name):
    cp, proposal = load(name)
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported") as caught:
        import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CUR_CP)
    assert caught.value.code == "undeclared_member"
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported") as caught:
        import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CUR_CP, control_plane_profile=None)
    assert caught.value.code == "undeclared_member"


@pytest.mark.parametrize("label", [P2_CP, I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_F5B_REVISION, I.CONTROL_PLANE_SECURITY_REVISION])
def test_p2_p4_and_earlier_labels_still_refuse_effective_configuration_with_and_without_the_selector(label):
    cp, proposal = load()
    # P2 shares the current record layout, so the member itself is what refuses; the P4 and earlier layouts refuse the current record already for other members.
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported" if label == P2_CP else None) as caught:
        import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=label)
    assert label != P2_CP or caught.value.code == "undeclared_member"
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector"):
        import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=label, control_plane_profile=SELECTOR)


@pytest.mark.parametrize("name", PLAIN_SCENARIOS)
def test_the_profile_is_not_inferred_a_plain_record_without_the_member_is_refused_under_it(name):
    cp = json.loads((PLAIN / name / "control_plane_run.json").read_text())
    proposal = json.loads((PLAIN / name / "proposal.json").read_text())
    export = json.loads((PLAIN / name / "runtime_export.json").read_text())
    assert all("effective_configuration" not in d["binding"]["runtime_authority"] for d in cp["decisions"])
    refused(cp, proposal, "effective_configuration is missing", "schema_violation")
    refused(cp, proposal, "effective_configuration is missing", "schema_violation", export=export)
    # and the same plain record is still accepted by the plain current profile (unchanged behaviour)
    assert import_bounded_workflow(copy.deepcopy(cp), proposal=proposal, moltbot_export=copy.deepcopy(export), control_plane_revision=CUR_CP).import_reports[0].adapter_profile == I.BOUNDED_CUR_PROFILE


def test_presence_of_the_member_alone_never_selects_the_profile():
    cp, proposal = load()
    with pytest.raises(ImportContractError) as caught:
        import_bounded_workflow(copy.deepcopy(cp), proposal=proposal, control_plane_revision=CUR_CP)
    assert caught.value.code == "undeclared_member"


def test_a_historical_runtime_export_or_a_mixed_pair_is_still_refused_under_the_profile():
    cp, proposal = load()
    export = json.loads((PLAIN / "valid" / "runtime_export.json").read_text())
    historical = copy.deepcopy(export)
    historical["repository"]["revision"] = I.MOLTBOT_P2_REVISION
    historical["provenance"]["source_asserted"]["repository_revision"] = I.MOLTBOT_P2_REVISION
    refused(cp, proposal, "combination", export=historical)


# ------------------------------------------------------------------------------------------------ missing
def test_a_missing_member_on_an_authorized_decision_is_refused_under_the_profile():
    cp, proposal = load()
    del cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]
    refused(cp, proposal, "effective_configuration is missing", "schema_violation")


def test_a_null_or_empty_member_is_refused():
    for value in (None, {}, [], "", 0):
        cp, proposal = load()
        cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"] = value
        refused(cp, proposal, "effective_configuration invalid")


def test_a_member_on_a_decision_that_is_not_authorized_is_refused():
    cp, proposal = load()
    cp["decisions"][0]["result"] = "hold"
    cp["decisions"][0]["reasons"] = ["required_input_not_read"]
    refused(cp, proposal, "runtime authority fields unsupported", "undeclared_member")  # refused by the closed member set itself, before the profile checker


# ------------------------------------------------------------------------------------------------ forged
def _flip(digest):
    return digest[:-1] + ("0" if digest[-1] != "0" else "1")


def test_a_forged_digest_is_refused():
    cp, proposal = load()
    member(cp)["digest"] = _flip(member(cp)["digest"])
    refused(cp, proposal, "invalid: invalid:digest_mismatch|effective_configuration invalid", "schema_violation")


@pytest.mark.parametrize("path", [("f4_scalars", "status_max_age_seconds"), ("other_scalars", "identity_max_age_seconds"), ("observation_policy", "max_age_seconds"),
                                  ("scope", "consumer_id"), ("scope", "institution_id"), ("scope", "authority_domain")])
def test_tampered_members_with_the_original_digest_are_refused(path):
    cp, proposal = load()
    ec = member(cp)
    value = ec["members"][path[0]][path[1]]
    ec["members"][path[0]][path[1]] = value + 1 if type(value) is int else value + "x"
    refused(cp, proposal, "invalid:digest_mismatch", "schema_violation")


def test_a_tampered_family_digest_or_dropped_family_with_the_original_digest_is_refused():
    cp, proposal = load()
    member(cp)["members"]["families"][0]["effective_policy_digest"] = "sha256:" + "a" * 64
    refused(cp, proposal, "invalid:digest_mismatch")
    cp, proposal = load()
    member(cp)["members"]["families"].pop()
    refused(cp, proposal, "invalid:digest_mismatch")


def test_a_swapped_member_from_another_configuration_with_its_own_valid_digest_is_still_bound_to_this_decisions_scope_and_profile():
    """A member lifted from a different governed decision is internally valid; it is refused when it does not agree with THIS decision (catalogue digest)."""
    cp, proposal = load("governed_executed")
    other, _ = load("governed_age_only")
    assert EC.record_defect(member(other)) is None
    cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"] = copy.deepcopy(member(other))
    refused(cp, proposal, "effective_profile_digest differs from catalogue_digest", "schema_violation")


def test_scope_must_agree_with_the_proposal_and_the_decision_even_when_the_digest_is_recomputed():
    cp, proposal = load()
    refused(reseal(cp, lambda m: m["scope"].__setitem__("tenant_id", "tenant-beta")), proposal, "differs from the decision's binding.tenant_id", "schema_violation")
    refused(reseal(cp, lambda m: m["scope"].__setitem__("action_id", "urn:cognous:action:other")), proposal, "scope.action_id differs", "schema_violation")
    # a proposal that names another tenant or action than the configuration's scope
    wrong = copy.deepcopy(proposal)
    wrong["tenant_id"] = "tenant-beta"
    refused(cp, wrong, "differs from the proposal", "schema_violation")


def test_effective_profile_digest_must_equal_the_decisions_catalogue_digest_even_when_resealed():
    cp, proposal = load()
    refused(reseal(cp, lambda m: m.__setitem__("effective_profile_digest", "sha256:" + "b" * 64)), proposal, "differs from catalogue_digest", "schema_violation")
    cp2 = copy.deepcopy(cp)
    cp2["decisions"][0]["binding"]["runtime_authority"]["catalogue_digest"] = "sha256:" + "b" * 64
    refused(cp2, proposal, "differs from catalogue_digest")


def test_known_non_detection_a_self_consistent_edit_of_a_free_value_is_not_detectable_from_the_record():
    """HONEST LIMIT: the digest is a redundant commitment over unsigned local JSON. Editing a scalar and recomputing the digest yields a valid-looking member that
    Replay cannot distinguish from the configuration actually in force; the Control Plane itself offers no stronger guarantee (it guards drift, not a party who can rewrite the store)."""
    cp, proposal = load()
    forged = reseal(cp, lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", m["f4_scalars"]["status_max_age_seconds"] + 1))
    assert member(forged)["digest"] != member(cp)["digest"]
    assert run(forged, proposal).import_reports[0].adapter_profile == GOVERNED_PROFILE


# ------------------------------------------------------------------------------------------------ unsupported / malformed shape (digest recomputed so only the shape is judged)
@pytest.mark.parametrize("version", ["effective-configuration-binding/0.2", "effective-configuration-binding/0.10", "effective-configuration-binding/0.1 ", "Effective-Configuration-Binding/0.1",
                                     "effective-configuration-binding", "latest", "", None, 1, 0.1, ["effective-configuration-binding/0.1"]])
def test_an_unsupported_version_is_refused(version):
    cp, proposal = load()
    member(cp)["version"] = version
    refused(cp, proposal, "effective_configuration (version unsupported|invalid)", "schema_violation" if type(version) is str else None)


def test_a_resealed_member_of_an_unsupported_version_is_refused_even_when_its_digest_is_consistent_with_that_version():
    cp, proposal = load()
    forged = copy.deepcopy(cp)
    ec = member(forged)
    ec["version"] = "effective-configuration-binding/0.2"
    body = {"domain": DOMAIN, "version": ec["version"], **ec["members"]}
    ec["digest"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    assert EC.digest_of(ec["version"], ec["members"]) == ec["digest"]
    refused(forged, proposal, "version unsupported", "schema_violation")


def test_a_str_subclass_equal_to_the_selector_is_refused():
    class Sneaky(str):
        pass
    cp, proposal = load()
    refused(cp, proposal, "unsupported Control Plane profile selector", selector=Sneaky(SELECTOR))


def test_extra_and_missing_record_keys_are_refused():
    cp, proposal = load()
    member(cp)["extra"] = 1
    refused(cp, proposal, "effective_configuration invalid", "undeclared_member")
    for key in ("version", "digest", "members"):
        cp, proposal = load()
        del member(cp)[key]
        refused(cp, proposal, "effective_configuration (invalid|version unsupported)")


SHAPE_MUTATIONS = {
    "extra_member_key": lambda m: m.__setitem__("extra", 1),
    "missing_member_key": lambda m: m.pop("host_profile_digest"),
    "members_not_a_dict": None,  # handled separately
    "scope_extra_key": lambda m: m["scope"].__setitem__("extra", "x"),
    "scope_missing_key": lambda m: m["scope"].pop("tenant_id"),
    "scope_empty_value": lambda m: m["scope"].__setitem__("tenant_id", ""),
    "scope_non_text": lambda m: m["scope"].__setitem__("tenant_id", 1),
    "host_digest_bad_hex": lambda m: m.__setitem__("host_profile_digest", "sha256:" + "G" * 64),
    "host_digest_uppercase": lambda m: m.__setitem__("host_profile_digest", "sha256:" + "A" * 64),
    "host_digest_zero": lambda m: m.__setitem__("host_profile_digest", "sha256:" + "0" * 64),
    "host_digest_short": lambda m: m.__setitem__("host_profile_digest", "sha256:abc"),
    "effective_digest_not_text": lambda m: m.__setitem__("effective_profile_digest", 5),
    "f4_scalar_bool": lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", True),
    "f4_scalar_float": lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", 60.0),
    "f4_scalar_string": lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", "60"),
    "f4_scalar_negative": lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", -1),
    "f4_scalar_over_max": lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", 2147483648),
    "f4_extra_key": lambda m: m["f4_scalars"].__setitem__("extra", 1),
    "f4_missing_key": lambda m: m["f4_scalars"].pop("approval_max_age_seconds"),
    "other_scalar_bool": lambda m: m["other_scalars"].__setitem__("mandate_max_age_seconds", False),
    "other_missing_key": lambda m: m["other_scalars"].pop("identity_max_age_seconds"),
    "other_extra_key": lambda m: m["other_scalars"].__setitem__("extra", 1),
    "observation_float": lambda m: m["observation_policy"].__setitem__("max_age_seconds", 60.5),
    "observation_extra_key": lambda m: m["observation_policy"].__setitem__("extra", 1),
    "observation_empty_dict": lambda m: m.__setitem__("observation_policy", {}),
    "observation_wrong_type": lambda m: m.__setitem__("observation_policy", []),
    "families_not_a_list": lambda m: m.__setitem__("families", {}),
    "families_tuple_like_string": lambda m: m.__setitem__("families", "none"),
    "family_extra_key": lambda m: m["families"][0].__setitem__("extra", 1),
    "family_missing_key": lambda m: m["families"][0].pop("slot"),
    "family_unknown_slot": lambda m: m["families"][0].__setitem__("slot", "unknown_slot"),
    "family_wrong_family_id": lambda m: m["families"][0].__setitem__("family_id", "f5-observation-max-age-policy"),
    "family_wrong_contract_version": lambda m: m["families"][1].__setitem__("contract_version", "r08-v7"),
    "family_unsupported_contract_version": lambda m: m["families"][1].__setitem__("contract_version", "r09-v1"),
    "family_schema_revision_wrong": lambda m: m["families"][0].__setitem__("family_schema_revision", 2),
    "family_schema_revision_null": lambda m: m["families"][0].__setitem__("family_schema_revision", None),
    "family_schema_revision_bool": lambda m: m["families"][0].__setitem__("family_schema_revision", True),
    "family_policy_digest_zero": lambda m: m["families"][0].__setitem__("effective_policy_digest", "sha256:" + "0" * 64),
    "family_policy_digest_null": lambda m: m["families"][0].__setitem__("effective_policy_digest", None),
    "family_duplicate_slot": lambda m: m["families"].append(copy.deepcopy(m["families"][-1])),
    "family_out_of_order": lambda m: m["families"].reverse(),
    "family_row_not_a_dict": lambda m: m["families"].append("x"),
}


@pytest.mark.parametrize("name", sorted(k for k, v in SHAPE_MUTATIONS.items() if v is not None))
def test_a_malformed_or_unsupported_member_is_refused_even_with_a_valid_recomputed_digest(name):
    cp, proposal = load()
    forged = reseal(cp, SHAPE_MUTATIONS[name])
    refused(forged, proposal, "effective_configuration invalid", None)


@pytest.mark.parametrize("value", [[], "x", 1, None])
def test_members_that_are_not_a_dict_are_refused(value):
    cp, proposal = load()
    member(cp)["members"] = value
    refused(cp, proposal, "effective_configuration invalid")


def test_the_unreduced_family_set_of_each_real_fixture_is_exactly_the_declared_one():
    cp, _ = load("governed_executed")
    assert [r["slot"] for r in member(cp)["members"]["families"]] == ["anchor_deadline", "observation_max_age", "observation_clock_tolerance"]
    assert {(r["family_id"], r["contract_version"], r["family_schema_revision"]) for r in member(cp)["members"]["families"]} == {
        ("f5-anchor-deadline-to-inputs-policy", "r08-v8", 1), ("f5-observation-max-age-policy", "r08-v8", 1), ("f5-observation-clock-tolerance-policy", "r08-v8", 1)}
    cp, _ = load("governed_age_only")
    assert [r["slot"] for r in member(cp)["members"]["families"]] == ["observation_max_age"]


# ------------------------------------------------------------------------------------------------ conflicting configurations in one run
def _decision(cp, decision_id, ec):
    d = copy.deepcopy(cp["decisions"][0])
    d["decision_id"] = decision_id
    d["binding"]["runtime_authority"]["effective_configuration"] = copy.deepcopy(ec)
    d["binding"]["runtime_authority"]["catalogue_digest"] = ec["members"]["effective_profile_digest"]  # keep THIS decision self-consistent: only the conflict is judged
    return d


def _check(decisions, proposal):
    def refuse(message, code=None):
        raise ImportContractError(message, code)
    EC.check_run(decisions, proposal, refuse)


def test_two_different_configurations_in_one_run_are_refused_and_equal_ones_pass():
    """The single-proposal importer cannot carry two decisions, so the run-level rule is exercised on the checker itself with two REAL members."""
    a, proposal = load("governed_executed")
    b, _ = load("governed_age_only")
    _check([a["decisions"][0], _decision(a, "d2", member(a))], proposal)
    with pytest.raises(ImportContractError, match="conflicting effective_configuration") as caught:
        _check([a["decisions"][0], _decision(a, "d2", member(b))], proposal)
    assert caught.value.code == "schema_violation"
    # either order refuses
    with pytest.raises(ImportContractError):
        _check([_decision(a, "d2", member(b)), a["decisions"][0]], proposal)


def test_the_full_importer_refuses_a_two_decision_run_with_different_configurations_as_conflicting():
    cp, proposal = load()
    other, _ = load("governed_age_only")
    cp["decisions"].append(_decision(cp, "d2", member(other)))
    with pytest.raises(ImportContractError):
        run(cp, proposal)


def test_the_run_level_checker_refuses_missing_and_unauthorized_members():
    a, proposal = load()
    bare = copy.deepcopy(a["decisions"][0])
    del bare["binding"]["runtime_authority"]["effective_configuration"]
    with pytest.raises(ImportContractError, match="missing"):
        _check([bare], proposal)
    hold = copy.deepcopy(a["decisions"][0])
    hold["result"] = "hold"
    with pytest.raises(ImportContractError, match="not authorized"):
        _check([hold], proposal)
    _check([], proposal)  # no decision: nothing to bind


# ------------------------------------------------------------------------------------------------ the explicitly unsupported scope stays refused under the profile
def test_policy_binding_members_remain_refused_under_the_profile():
    for members in ({"approval_commitment_version": "approval-commitment/0.2"}, {"policy_generation": 1}, {"policy_activation_ref": "sha256:" + "c" * 64}):
        cp, proposal = load()
        cp["decisions"][0]["binding"]["runtime_authority"].update(members)
        refused(cp, proposal, "runtime authority fields unsupported", "undeclared_member")


def test_an_unknown_runtime_authority_member_remains_refused_under_the_profile():
    cp, proposal = load()
    cp["decisions"][0]["binding"]["runtime_authority"]["x_extra"] = "1"
    refused(cp, proposal, "runtime authority fields unsupported", "undeclared_member")


def test_reason_vocabulary_0_3_remains_refused_under_the_profile():
    cp, proposal = load()
    cp["decisions"][0]["reason_vocabulary_version"] = "runtime-authority-reasons/0.3"
    refused(cp, proposal)


def test_a_missing_base_member_remains_refused_under_the_profile():
    cp, proposal = load()
    del cp["decisions"][0]["binding"]["runtime_authority"]["catalogue_digest"]
    refused(cp, proposal, "runtime authority fields unsupported")


def test_selection_refusal_and_authorization_pin_evidence_remain_refused_under_the_profile():
    cp, proposal = load()
    export = json.loads((PLAIN / "revoked" / "runtime_export.json").read_text())
    for member_name in ("selection_refusal", "authorization_pin"):
        forged = copy.deepcopy(export)
        forged["control_plane_evidence"][member_name] = {"version": "0.1"}
        forged["execution_result"]["control_plane_evidence"][member_name] = {"version": "0.1"}
        with pytest.raises(ImportContractError):
            run(cp, proposal, export=forged)


# ------------------------------------------------------------------------------------------------ retained-bundle revalidation
def test_a_retained_bundle_revalidates_only_with_the_selector_recorded_in_its_metadata():
    from agent_replay_bundle.refusal_evidence import extend_retained_inputs
    cp, proposal = load("governed_executed")
    dumped = run(cp, proposal).model_dump(mode="json")
    by = lambda kind: [r["data"] for r in sorted(dumped["records"], key=lambda r: r["source_sequence"]) if r["record_type"] == kind]
    rebuilt = extend_retained_inputs({"run_id": dumped["run_id"], "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
                                      "observations": by("effect_observation"), "reconciliations": by("reconciliation")}, dumped)
    meta = dumped["metadata"]
    again = import_bounded_workflow(copy.deepcopy(rebuilt), proposal=by("runtime_proposal")[0], control_plane_revision=meta["control_plane_revision"],
                                    control_plane_profile=meta["control_plane_profile"])
    assert again.import_reports[0].adapter_profile == GOVERNED_PROFILE
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported"):
        import_bounded_workflow(copy.deepcopy(rebuilt), proposal=by("runtime_proposal")[0], control_plane_revision=meta["control_plane_revision"])
    damaged = copy.deepcopy(rebuilt)
    member(damaged)["members"]["f4_scalars"]["status_max_age_seconds"] += 1
    with pytest.raises(ImportContractError, match="invalid:digest_mismatch"):
        import_bounded_workflow(damaged, proposal=by("runtime_proposal")[0], control_plane_revision=meta["control_plane_revision"],
                                control_plane_profile=meta["control_plane_profile"])


# ------------------------------------------------------------------------------------------------ what the profile does NOT verify (stated, not hidden)
def test_without_a_proposal_the_tenant_binding_is_unverified_and_the_registry_revision_is_never_carried():
    cp, _ = load()
    bundle = run(cp, None)  # accepted: the proposal-dependent cross-check is skipped, not faked
    assert bundle.import_reports[0].adapter_profile == GOVERNED_PROFILE
    text = json.dumps(member(cp))
    # No Registry source revision, commit, signature, trust snapshot or selection id is part of the member (the Control Plane excludes them on purpose).
    for absent in ("a40fe755", "registry_revision", "signature", "trust", "selection_id", "selection_epoch", "evaluated_at"):
        assert absent not in text
    assert bundle.metadata["effective_configuration_verification"] == "internal_consistency_only_registry_source_revision_unverified"


def test_no_other_generation_imports_a_governed_record_even_with_the_member_removed_and_the_label_changed():
    """Relabelling or stripping is not a way in: P2/P4 labels with the member present are refused; removing the member is the plain record and is a different artefact."""
    cp, proposal = load()
    for label in HISTORICAL_LABELS:
        with pytest.raises(ImportContractError):
            import_bounded_workflow(copy.deepcopy(cp), proposal=proposal, control_plane_revision=label)


# ------------------------------------------------------------------------------------------------ F1 / F2 (review of PR #81)
def test_the_real_binding_carries_the_tenant_the_member_is_bound_to():
    for name in SCENARIOS:
        cp, proposal = load(name)
        assert cp["decisions"][0]["binding"]["tenant_id"] == member(cp)["members"]["scope"]["tenant_id"] == proposal["tenant_id"] == "tenant-alpha"


@pytest.mark.parametrize("with_proposal", [True, False])
def test_a_resealed_foreign_tenant_is_refused_with_and_without_a_proposal(with_proposal):
    cp, proposal = load()
    forged = reseal(cp, lambda m: m["scope"].__setitem__("tenant_id", "tenant-evil"))
    refused(forged, proposal if with_proposal else None, "differs from the decision's binding.tenant_id|differs from the proposal", "schema_violation")
    if not with_proposal:
        refused(forged, None, "binding.tenant_id", "schema_violation")


@pytest.mark.parametrize("with_proposal", [True, False])
def test_member_and_proposal_agreeing_on_a_tenant_the_decision_does_not_carry_is_refused(with_proposal):
    cp, proposal = load()
    cp["decisions"][0]["binding"]["tenant_id"] = "tenant-other"
    refused(cp, proposal if with_proposal else None, "binding.tenant_id", "schema_violation")
    cp, proposal = load()
    del cp["decisions"][0]["binding"]["tenant_id"]
    refused(cp, proposal if with_proposal else None, "binding.tenant_id", "schema_violation")


def test_a_null_observation_policy_is_a_valid_member_the_control_plane_permits():
    cp, proposal = load()
    ok = reseal(cp, lambda m: m.__setitem__("observation_policy", None))
    assert run(ok, proposal).import_reports[0].adapter_profile == GOVERNED_PROFILE
    assert EC.record_defect(member(ok)) is None


@pytest.mark.parametrize("edit", [lambda m: m["scope"].__setitem__("institution_id", "urn:cognous:institution:other"),
                                  lambda m: m["scope"].__setitem__("consumer_id", "consumer-other"),
                                  lambda m: m["scope"].__setitem__("authority_domain", "other-domain"),
                                  lambda m: m.__setitem__("host_profile_digest", "sha256:" + "d" * 64),
                                  lambda m: m["families"][0].__setitem__("effective_policy_digest", "sha256:" + "e" * 64),
                                  lambda m: m.__setitem__("families", [])])
def test_known_non_detection_fields_no_decision_field_carries_pass_when_resealed(edit):
    """EXPLICIT NON-DETECTION: institution_id, consumer_id, authority_domain, host_profile_digest, family digests and the family set are not carried by any decision
    field nor recomputable from the record; a resealed edit is accepted. Documented in effective_configuration.py and the PR body."""
    cp, proposal = load()
    assert run(reseal(cp, edit), proposal).import_reports[0].adapter_profile == GOVERNED_PROFILE


def test_a_null_effective_profile_digest_removes_the_catalogue_tie_known_non_detection():
    cp, proposal = load()
    assert run(reseal(cp, lambda m: m.__setitem__("effective_profile_digest", None)), proposal).import_reports[0].adapter_profile == GOVERNED_PROFILE
