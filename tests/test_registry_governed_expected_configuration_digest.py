"""Caller-trusted expected effective-configuration digest (sprint OCS-254-R1B, controls R1-P01..R1-N09).

``import_bounded_workflow(..., expected_effective_configuration_digest=...)`` is valid only with the explicitly selected Registry-governed profile. Omitted, the import is
structural-only exactly as before. Passed at all (None and "" included) the import is fail-closed and succeeds only when the record's recomputed effective-configuration
digest equals the digest the CALLER trusts. Success is labelled ``caller_trusted_configuration_match``: NOT Registry authentication, the Registry origin and revision stay
unverified, and Replay cannot tell where the caller got the string (R1-N03 pins that boundary; it is not independent evidence).
"""
import copy
import hashlib
import json

import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import effective_configuration as EC
from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import import_bounded_workflow

from .test_registry_governed_effective_configuration import (CUR_CP, DOMAIN, GOVERNED_PROFILE, HISTORICAL_LABELS, P2_CP, PLAIN, SELECTOR, VERSION, load, member, reseal)

# Independently established constant: the digest the real Control Plane b19c47dd recorded for the genuine governed workflow (host config obs 300/5, Registry-selected
# anchor/age 60/tol 2, consumer-test / tenant-alpha / refund-issue-routine-v1), reproduced by a separate process (Worker B derivation contract, S0/S3 probe record).
# It is hard-coded on purpose and is NEVER read from the record under test.
PINNED = "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7"
STRUCTURAL = "internal_consistency_only_registry_source_revision_unverified"
FORGED_FAMILY = "sha256:" + "3" * 64


def go(cp, proposal, **kw):
    kw.setdefault("control_plane_revision", CUR_CP)
    kw.setdefault("control_plane_profile", SELECTOR)
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), **kw)


def refuses(cp, proposal, code, match=None, **kw):
    with pytest.raises(ImportContractError, match=match) as caught:
        go(cp, proposal, **kw)
    assert caught.value.code == code
    return caught.value


def digest_for(members):
    """Independent of the code under test (same canonical form the Control Plane uses)."""
    body = {"domain": DOMAIN, "version": VERSION, **members}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def resealed_family_substitution(cp):
    """The S3 probe's replay_resealed_substitution: families[0].effective_policy_digest := sha256:3333..., digest recomputed."""
    return reseal(cp, lambda m: m["families"][0].__setitem__("effective_policy_digest", FORGED_FAMILY))


def assert_trusted_marker(bundle):
    meta = bundle.metadata
    assert meta["effective_configuration_verification"] == "caller_trusted_configuration_match"
    assert meta["registry_authenticated"] is False and meta["registry_origin"] == "registry_origin_unverified"
    assert meta["control_plane_profile"] == SELECTOR


# ------------------------------------------------------------------------------------------------ positives
def test_R1_P01_genuine_record_with_the_independently_pinned_digest_is_accepted_as_caller_trusted_match():
    cp, proposal = load("governed_executed")
    assert member(cp)["digest"] == PINNED  # the fixture IS the genuine record; the constant above was not derived from it
    bundle = go(cp, proposal, expected_effective_configuration_digest=PINNED)
    assert bundle.import_reports[0].adapter_profile == GOVERNED_PROFILE
    assert_trusted_marker(bundle)
    assert [r.data for r in bundle.records if r.record_type == "runtime_decision"] == cp["decisions"]  # decision retained verbatim, nothing altered


@pytest.mark.parametrize("name", ["governed_executed", "governed_binding_changed", "governed_decided_only"])
def test_R1_P01b_every_genuine_scenario_of_the_pinned_configuration_matches(name):
    cp, proposal = load(name)
    assert_trusted_marker(go(cp, proposal, expected_effective_configuration_digest=PINNED))


def test_R1_P01c_a_different_genuine_configuration_matches_only_its_own_independently_recorded_digest():
    cp, proposal = load("governed_age_only")
    age_only = "sha256:9b83d2665fd1a0e3843385408c362c2f49863651c6d7406ee0747e3e39954c42"  # recorded by the real Control Plane for the age-61 configuration
    assert_trusted_marker(go(cp, proposal, expected_effective_configuration_digest=age_only))
    refuses(cp, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=PINNED)


def test_R1_P02_default_import_is_unchanged_structural_only_with_the_unqualified_marker():
    cp, proposal = load("governed_executed")
    bundle = go(cp, proposal)
    assert bundle.metadata["effective_configuration_verification"] == STRUCTURAL
    assert "registry_authenticated" not in bundle.metadata and "registry_origin" not in bundle.metadata
    assert bundle.import_reports[0].adapter_profile == GOVERNED_PROFILE
    # the trusted-match report differs from the structural one in the verification metadata only
    trusted = go(cp, proposal, expected_effective_configuration_digest=PINNED).model_dump(mode="json")
    plain = bundle.model_dump(mode="json")
    for dumped in (trusted, plain):
        for key in ("effective_configuration_verification", "registry_authenticated", "registry_origin"):
            dumped["metadata"].pop(key, None)
        for key in ("bundle_id", "generated_at"):  # volatile per call
            dumped.pop(key)
    assert trusted == plain


def test_R1_P03_genuine_tenant_action_and_catalogue_identity_pass_under_trusted_match():
    cp, proposal = load("governed_executed")
    scope = member(cp)["members"]["scope"]
    decision = cp["decisions"][0]
    assert (scope["tenant_id"], scope["action_id"]) == ("tenant-alpha", "urn:cognous:action:refund-issue-routine-v1")
    assert (decision["binding"]["tenant_id"], decision["binding"]["action_id"]) == (scope["tenant_id"], scope["action_id"])
    assert (proposal["tenant_id"], proposal["action_id"]) == (scope["tenant_id"], scope["action_id"])
    assert member(cp)["members"]["effective_profile_digest"] == decision["binding"]["runtime_authority"]["catalogue_digest"]
    assert_trusted_marker(go(cp, proposal, expected_effective_configuration_digest=PINNED))


# ------------------------------------------------------------------------------------------------ negatives
def test_R1_N01_substituted_configuration_with_a_stale_digest_is_refused_by_the_existing_check_in_both_modes():
    cp, proposal = load()
    stale = copy.deepcopy(cp)
    member(stale)["members"]["families"][0]["effective_policy_digest"] = FORGED_FAMILY  # digest NOT recomputed
    with pytest.raises(ImportContractError, match="invalid:digest_mismatch") as default_mode:
        go(stale, proposal)
    assert default_mode.value.code == "schema_violation"
    with pytest.raises(ImportContractError, match="invalid:digest_mismatch") as trusted_mode:
        go(stale, proposal, expected_effective_configuration_digest=PINNED)
    assert trusted_mode.value.code == "schema_violation"  # the integrity refusal comes first (order 3 before 5) and keeps its existing semantics


def test_R1_N02_resealed_substitution_is_refused_under_trusted_match_and_still_accepted_by_default():
    cp, proposal = load()
    forged = resealed_family_substitution(cp)
    assert member(forged)["digest"] != PINNED and EC.record_defect(member(forged)) is None  # a perfectly self-consistent record
    # documented structural-only NON-DETECTION, pinned: the default mode cannot see it (the S3 probe's NON_DETECTION_RECORDED)
    default = go(forged, proposal)
    assert default.metadata["effective_configuration_verification"] == STRUCTURAL
    # trusted-match mode refuses it, with the typed mismatch reason, before any imported decision exists
    error = refuses(forged, proposal, "effective_configuration_expected_mismatch", "differs from the caller-trusted expected digest", expected_effective_configuration_digest=PINNED)
    assert "typed refusal profile" in str(error)


@pytest.mark.parametrize("mutate", [
    lambda m: m["f4_scalars"].__setitem__("status_max_age_seconds", m["f4_scalars"]["status_max_age_seconds"] + 1),
    lambda m: m["observation_policy"].__setitem__("max_age_seconds", m["observation_policy"]["max_age_seconds"] + 1),
    lambda m: m.__setitem__("host_profile_digest", None),
    lambda m: m["scope"].__setitem__("institution_id", "urn:cognous:institution:other"),
    lambda m: m["scope"].__setitem__("authority_domain", "other-domain"),
    lambda m: m["scope"].__setitem__("consumer_id", "consumer-other"),
    lambda m: m["families"].pop(),
], ids=["scalar", "observation_policy", "host_digest", "institution", "authority_domain", "consumer", "family_dropped"])
def test_R1_N02b_other_known_non_detections_are_refused_under_trusted_match(mutate):
    cp, proposal = load()
    forged = reseal(cp, mutate)
    go(forged, proposal)  # default mode: accepted (pinned non-detection)
    refuses(forged, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=PINNED)


def test_R1_N02c_a_resealed_age_change_with_the_profile_tie_removed_is_refused_under_trusted_match():
    cp, proposal = load()
    forged = reseal(cp, lambda m: (m["observation_policy"].__setitem__("max_age_seconds", 61), m.__setitem__("effective_profile_digest", None)))
    go(forged, proposal)
    refuses(forged, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=PINNED)


def test_R1_N03_NON_INDEPENDENT_setup_an_expected_digest_copied_from_the_forged_record_is_accepted():
    """NOT independent evidence. Replay receives only a string and cannot infer its provenance: if the caller derives the expected digest from the very record under
    test (or from the same untrusted store), the forgery matches itself. That is OUTSIDE the trust boundary of this parameter and is documented, not detected."""
    cp, proposal = load()
    forged = resealed_family_substitution(cp)
    copied = member(forged)["digest"]
    assert copied != PINNED
    bundle = go(forged, proposal, expected_effective_configuration_digest=copied)
    assert_trusted_marker(bundle)  # the label says CALLER-trusted: the caller trusted the wrong thing
    assert bundle.metadata["registry_authenticated"] is False


def test_R1_N04_a_wrong_independent_expected_digest_is_refused():
    cp, proposal = load()
    for wrong in ("sha256:" + "a" * 64, "sha256:" + "1" * 64, "sha256:9b83d2665fd1a0e3843385408c362c2f49863651c6d7406ee0747e3e39954c42"):
        refuses(cp, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=wrong)
    # one hex digit away from the genuine value
    flipped = PINNED[:-1] + ("0" if PINNED[-1] != "0" else "1")
    refuses(cp, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=flipped)


def test_R1_N05_an_explicit_missing_expected_digest_is_refused_not_downgraded():
    cp, proposal = load()
    refuses(cp, proposal, "effective_configuration_expected_missing", expected_effective_configuration_digest=None)


@pytest.mark.parametrize("bad", ["sha256:" + "g" * 64, "SHA256:" + "a" * 64, "Sha256:" + "a" * 64, "sha256:" + "A" * 64, PINNED.upper(), "sha256:" + "a" * 63, "sha256:" + "a" * 65,
                                 "a" * 64, "sha512:" + "a" * 64, "sha256:" + "0" * 64, "", " ", PINNED + "\n", " " + PINNED, PINNED + " ", "sha256:" + "a" * 32 + "١" * 32])
def test_R1_N06_malformed_expected_digests_are_refused(bad):
    cp, proposal = load()
    refuses(cp, proposal, "effective_configuration_expected_malformed", expected_effective_configuration_digest=bad)


@pytest.mark.parametrize("bad", [0, 1, True, False, b"sha256:" + b"a" * 64, ["sha256:" + "a" * 64], {"digest": PINNED}, 3.5, object()])
def test_R1_N06b_non_string_expected_values_are_refused(bad):
    cp, proposal = load()
    refuses(cp, proposal, "effective_configuration_expected_malformed", expected_effective_configuration_digest=bad)


def test_R1_N06c_a_string_subclass_is_refused():
    class S(str):
        pass
    cp, proposal = load()
    refuses(cp, proposal, "effective_configuration_expected_malformed", expected_effective_configuration_digest=S(PINNED))


def test_R1_N06d_a_malformed_expected_never_reaches_the_record():
    """Caller bug, refused before the record is read: even an unreadable record yields the expected-digest reason."""
    with pytest.raises(ImportContractError) as caught:
        import_bounded_workflow({"not": "a record"}, control_plane_revision=CUR_CP, control_plane_profile=SELECTOR, expected_effective_configuration_digest="nope")
    assert caught.value.code == "effective_configuration_expected_malformed"


def test_R1_N07_wrong_tenant_or_action_is_refused_via_the_digest():
    cp, proposal = load()
    members = copy.deepcopy(member(cp)["members"])
    assert digest_for(members) == PINNED  # the independent builder agrees with the pinned vector
    for field, other in (("tenant_id", "tenant-beta"), ("action_id", "urn:cognous:action:other-v1"), ("consumer_id", "consumer-other"),
                         ("institution_id", "urn:cognous:institution:other"), ("authority_domain", "other-domain")):
        wrong = copy.deepcopy(members)
        wrong["scope"][field] = other
        expected = digest_for(wrong)
        assert expected != PINNED
        refuses(cp, proposal, "effective_configuration_expected_mismatch", expected_effective_configuration_digest=expected)


@pytest.mark.parametrize("selector", [None])
@pytest.mark.parametrize("revision", [CUR_CP, P2_CP, *HISTORICAL_LABELS[1:], I.CONTROL_PLANE_REVISION])
def test_R1_N08_the_parameter_without_the_governed_selector_is_refused_as_unsupported(selector, revision):
    cp, proposal = load()
    for value in (PINNED, None, "", "nope"):
        refuses(cp, proposal, "effective_configuration_expected_unsupported_profile", control_plane_profile=selector, control_plane_revision=revision,
                expected_effective_configuration_digest=value)


@pytest.mark.parametrize("selector,revision", [(SELECTOR, P2_CP), (SELECTOR, I.CONTROL_PLANE_P4_REVISION), (SELECTOR, I.CONTROL_PLANE_F5B_REVISION),
                                               (SELECTOR, I.CONTROL_PLANE_SECURITY_REVISION), (SELECTOR, I.CONTROL_PLANE_REVISION),
                                               ("registry-governed-effective-configuration/0.2", CUR_CP), ("latest", CUR_CP), ("", CUR_CP),
                                               (SELECTOR + " ", CUR_CP), (GOVERNED_PROFILE, CUR_CP)])
def test_R1_N08b_mixed_generation_or_unsupported_selector_is_refused_with_the_parameter(selector, revision):
    cp, proposal = load()
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector"):
        go(cp, proposal, control_plane_profile=selector, control_plane_revision=revision, expected_effective_configuration_digest=PINNED)


def test_R1_N08c_the_parameter_with_a_plain_record_and_no_selector_does_not_import_it():
    plain = PLAIN / "valid"
    cp = json.loads((plain / "control_plane_run.json").read_text())
    proposal = json.loads((plain / "proposal.json").read_text())
    refuses(cp, proposal, "effective_configuration_expected_unsupported_profile", control_plane_profile=None, expected_effective_configuration_digest=PINNED)
    # and with the selector a plain record (no member on an authorized decision) is refused as before, not accepted on a trusted-match path
    with pytest.raises(ImportContractError, match="effective_configuration is missing on an authorized decision"):
        go(cp, proposal, expected_effective_configuration_digest=PINNED)


def test_R1_N08d_a_governed_record_without_the_member_is_refused_in_trusted_match_mode():
    cp, proposal = load()
    stripped = copy.deepcopy(cp)
    del stripped["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]
    with pytest.raises(ImportContractError, match="effective_configuration is missing on an authorized decision"):
        go(stripped, proposal, expected_effective_configuration_digest=PINNED)


def test_R1_N08e_trusted_match_with_no_authorized_decision_fails_closed():
    refusals = []
    def refuse(message, code=None):
        refusals.append(code)
        raise ImportContractError(message, code)
    with pytest.raises(ImportContractError):
        EC.check_run([], None, refuse, expected=PINNED)
    assert refusals == ["effective_configuration_record_missing"]
    EC.check_run([], None, refuse)  # structural-only: nothing to check, unchanged


def test_R1_N09_an_explicit_none_cannot_become_a_structural_only_acceptance():
    cp, proposal = load()
    assert go(cp, proposal).metadata["effective_configuration_verification"] == STRUCTURAL  # omitted: structural-only
    for forged in (cp, resealed_family_substitution(cp)):
        refuses(forged, proposal, "effective_configuration_expected_missing", expected_effective_configuration_digest=None)
    # passing the parameter at all (empty, falsy, wrong type) is trusted-match: none of these is accepted
    for value in (None, "", 0, False, b"", [], {}):
        with pytest.raises(ImportContractError):
            go(cp, proposal, expected_effective_configuration_digest=value)


def test_R1_N09b_the_unset_sentinel_is_private_and_not_a_valid_expected_value():
    cp, proposal = load()
    refuses(cp, proposal, "effective_configuration_expected_malformed", expected_effective_configuration_digest=object())


def test_the_parameter_is_keyword_only_and_the_only_new_public_signature_change():
    import inspect
    params = inspect.signature(import_bounded_workflow).parameters
    assert list(params) == ["control_plane_record", "proposal", "moltbot_export", "control_plane_revision", "control_plane_profile", "expected_effective_configuration_digest"]
    assert params["expected_effective_configuration_digest"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["expected_effective_configuration_digest"].default is I._EXPECTED_UNSET


def test_refusal_semantics_of_existing_negative_records_are_preserved_in_trusted_mode():
    """A record the structural-only mode refuses is refused in trusted-match mode for the SAME reason and code (the expected digest never masks or replaces it)."""
    cp, proposal = load()
    cases = []
    bad_tenant = copy.deepcopy(cp)
    bad_tenant["decisions"][0]["binding"]["tenant_id"] = "tenant-beta"
    cases.append(bad_tenant)
    bad_catalogue = copy.deepcopy(cp)
    bad_catalogue["decisions"][0]["binding"]["runtime_authority"]["catalogue_digest"] = "sha256:" + "b" * 64
    cases.append(bad_catalogue)
    extra = copy.deepcopy(cp)
    member(extra)["provenance"] = {"registry_revision": "a40fe755"}
    cases.append(extra)
    for case in cases:
        with pytest.raises(ImportContractError) as default_mode:
            go(case, proposal)
        with pytest.raises(ImportContractError) as trusted_mode:
            go(case, proposal, expected_effective_configuration_digest=PINNED)
        assert (str(trusted_mode.value), trusted_mode.value.code) == (str(default_mode.value), default_mode.value.code)
