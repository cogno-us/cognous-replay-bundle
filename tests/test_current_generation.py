"""Current generation (CUR): Control Plane b19c47dd paired with the runtime f7a55e2a, added beside the Programme-2 generation.

The valid cases are REAL run records and exports written by the Control Plane's and the runtime's own flows at pristine checkouts of
exactly those revisions (``tests/fixtures/current_generation``; provenance and capture script alongside). The nine plain scenarios
(executed, lost acknowledgement, revoked, unreadable, purpose closed, purpose reopened, tampered evidence, input dropped, race) are
imported and checked for content, not only acceptance.

What this proves: one exact CUR <-> CUR pairing, that the historical Programme-2 generation and the earlier ones are unchanged and
cannot be reached with a current record (and the reverse), that no other hash is accepted, and that the explicitly unsupported scope
stays refused fail-closed. What it does not prove: that the provenance labels are anything but caller-asserted, that any signer is
authentic, or that effective-grant digests re-derive. This is a PROVISIONAL DEVELOPMENT PIN, UNQUALIFIED, non-authorizing, like P2.
"""
import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import import_bounded_workflow

FIX = Path(__file__).parent / "fixtures" / "current_generation"
CUR_CP = "b19c47ddd020409d24e52e70b11359c46265edbb"
CUR_RT = "f7a55e2a8494801e49193f9f46935f0a971c248d"
CUR_MANIFEST = "fa170815ef96a54c233d0dd9da821b60debabf8b"
CUR_BOUNDED = "control-plane-current-stack@b19c47dd"
CUR_MOLTBOT = "moltbot-safe-executor-producer-2.0.0@f7a55e2a"
P2_CP = "7a4bcd40b3b49e61ff3c294dcca53b52f460b22c"
P2_RT = "c5e97e87dd239c821b1b4a406a55dcd03c5bc61f"
LABEL_01, LABEL_03 = "runtime-authority-reasons/0.1", "runtime-authority-reasons/0.3"
SCENARIOS = {  # name -> (execution status, retained refusal reasons or None)
    "valid": ("executed", None), "lost_ack": ("reconciled", None), "race": ("failed", None),
    "revoked": ("denied", ["grant_revoked"]), "unreadable": ("denied", ["status_unreadable"]),
    "purpose_closed": ("denied", ["purpose_closed"]), "purpose_reopened": ("denied", ["purpose_epoch_changed"]),
    "tampered_evidence": ("denied", ["evidence_signature_invalid"]), "input_dropped": ("denied", ["required_input_not_read"]),
}
# Shapes copied from real Control Plane b19c47dd records of the unsupported scope (registry-governed decision; policy-binding decision).
EFFECTIVE_CONFIGURATION = {"version": "effective-configuration-binding/0.1", "digest": "sha256:" + "1" * 64,
                           "members": {"scope": {"consumer_id": "consumer-test", "tenant_id": "tenant-alpha"}}}
POLICY_BINDING = {"approval_commitment_version": "approval-commitment/0.2", "policy_generation": 1, "policy_activation_ref": "sha256:" + "c" * 64}


def load(name="valid"):
    return tuple(json.loads((FIX / name / f).read_text()) for f in ("control_plane_run.json", "proposal.json", "runtime_export.json"))


def run(cp, proposal, executor, revision=CUR_CP):
    return import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal),
                                   moltbot_export=copy.deepcopy(executor) if executor is not None else None, control_plane_revision=revision)


def authority(cp):
    return [d["binding"]["runtime_authority"] for d in cp["decisions"] if d.get("binding")]


def refused(cp, proposal, executor, revision=CUR_CP, match=None):
    with pytest.raises(ImportContractError, match=match):
        run(cp, proposal, executor, revision)


# ------------------------------------------------------------------------------------------------ the exact pins
def test_the_current_generation_constants_are_exactly_these_and_p2_is_unchanged():
    assert (I.CONTROL_PLANE_CUR_REVISION, I.MOLTBOT_CUR_REVISION, I.MANIFEST_CUR_REVISION) == (CUR_CP, CUR_RT, CUR_MANIFEST)
    assert (I.BOUNDED_CUR_PROFILE, I.MOLTBOT_CUR_PROFILE) == (CUR_BOUNDED, CUR_MOLTBOT)
    assert (I.CONTROL_PLANE_P2_REVISION, I.MOLTBOT_P2_REVISION, I.MANIFEST_P2_REVISION) == (P2_CP, P2_RT, CUR_MANIFEST)
    assert (I.BOUNDED_P2_PROFILE, I.MOLTBOT_P2_PROFILE) == ("control-plane-programme2-profiles@7a4bcd40", "moltbot-safe-executor-producer-2.0.0@c5e97e87")
    assert len({CUR_CP, P2_CP, CUR_RT, P2_RT}) == 4 and len({CUR_BOUNDED, I.BOUNDED_P2_PROFILE, CUR_MOLTBOT, I.MOLTBOT_P2_PROFILE}) == 4


def test_the_current_pins_are_in_every_generation_set_beside_p2_and_nowhere_else():
    assert I.PROGRAMME2_CP_REVISIONS == frozenset({P2_CP, CUR_CP})
    assert CUR_CP in I.SECURITY_RUNTIME_CP_REVISIONS and CUR_CP in I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS and CUR_CP in I.PROGRAMME2_CP_REVISIONS
    assert I.SECURITY_RUNTIME_CP_REVISIONS == frozenset({I.CONTROL_PLANE_SECURITY_REVISION, I.CONTROL_PLANE_F5B_REVISION, I.CONTROL_PLANE_P4_REVISION, P2_CP, CUR_CP})
    assert I.SECURITY_RUNTIME_BOUNDED_PROFILES == frozenset({I.BOUNDED_SECURITY_PROFILE, I.BOUNDED_F5B_PROFILE, I.BOUNDED_P4_PROFILE,
                                                             "control-plane-programme2-profiles@7a4bcd40", CUR_BOUNDED,
                                                             "control-plane-current-stack-registry-governed-effective-configuration-0.1@b19c47dd"})
    assert CUR_MOLTBOT in I.STRICT_ACK_PROFILES and "moltbot-safe-executor-producer-2.0.0@c5e97e87" in I.STRICT_ACK_PROFILES
    assert I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS.count(CUR_CP) == 1 and I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS.count(P2_CP) == 1
    assert [r for r in I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS if r.startswith("b19c47dd")] == [CUR_CP]
    assert not any(v for k, v in vars(I).items() if isinstance(v, str) and ("b19c47dd" in v or "f7a55e2a" in v) and k not in {
        "CONTROL_PLANE_CUR_REVISION", "MOLTBOT_CUR_REVISION", "BOUNDED_CUR_PROFILE", "MOLTBOT_CUR_PROFILE", "BOUNDED_CUR_REGISTRY_GOVERNED_PROFILE"})


# ------------------------------------------------------------------------------------------------ the nine real scenarios
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_real_current_pair_is_accepted_and_its_content_retained(name):
    status, reasons = SCENARIOS[name]
    cp, proposal, executor = load(name)
    assert authority(cp) and all(set(a) == {"profile", "approval_commitment", "required_inputs_digest", "catalogue_digest",
                                            "expected_effective_grant_digest", "effective_grant_derivation_version"} for a in authority(cp))
    assert executor["repository"]["revision"] == CUR_RT and executor["execution_result"]["status"] == status
    bundle = run(cp, proposal, executor)
    assert bundle.status == "reconstruction_complete"
    assert [r.complete for r in bundle.import_reports] == [True] and bundle.import_reports[0].adapter_profile == CUR_BOUNDED
    assert {r.producer_profile_id for r in bundle.records if r.record_type in {"runtime_decision", "runtime_proposal"}} == {CUR_BOUNDED}
    (decision,) = [r.data for r in bundle.records if r.record_type == "runtime_decision"]
    assert decision == cp["decisions"][0] and decision["reason_vocabulary_version"] == LABEL_01
    assert [r.data for r in bundle.records if r.record_type == "runtime_proposal"] == [proposal]
    assert len([r for r in bundle.records if r.record_type == "control_plane_attempt_transition"]) == len(cp["attempts"])
    (result,) = [r.data for r in bundle.records if r.record_type == "execution_result"]
    assert result["status"] == status
    (evidence,) = [r.data for r in bundle.records if r.record_type == "executor_control_plane_evidence"]
    assert evidence == executor["control_plane_evidence"]
    if reasons is not None:
        assert evidence["refusal"]["reasons"] == reasons and result["attempted"] is False
        assert [r["reasons"] for r in cp["refusals"]] == [reasons]
    meta = bundle.metadata
    assert (meta["control_plane_revision"], meta["moltbot_safe_revision"], meta["manifest_revision"]) == (CUR_CP, CUR_RT, CUR_MANIFEST)
    assert meta["moltbot_producer_contract"]["profile_id"] == CUR_MOLTBOT
    assert meta["moltbot_producer_contract"]["compatible_control_plane_revisions"] == [CUR_CP]
    assert meta["executor_failure_reference_verification"] == "source_asserted_not_independently_verified"


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_real_current_record_without_executor_export_is_accepted(name):
    cp, proposal, _ = load(name)
    bundle = run(cp, proposal, None)
    assert bundle.status == "reconstruction_partial"  # no executor evidence: partial by design
    assert bundle.import_reports[0].adapter_profile == CUR_BOUNDED and bundle.metadata["moltbot_safe_revision"] is None and bundle.metadata["control_plane_revision"] == CUR_CP


def test_the_nine_scenarios_are_the_nine_fixtures():
    assert sorted(p.name for p in FIX.iterdir() if p.is_dir()) == sorted(SCENARIOS) and len(SCENARIOS) == 9


# ------------------------------------------------------------------------------------------------ labels and pairing
@pytest.mark.parametrize("label", [P2_CP, I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_SECURITY_REVISION, I.CONTROL_PLANE_F5B_REVISION])
def test_a_current_record_under_a_historical_label_is_refused(label):
    cp, proposal, executor = load()
    refused(cp, proposal, executor, label, "unsupported executor/Control Plane revision combination")


def test_p2_and_p4_labels_are_refused_for_a_current_export_and_cp_alone_keeps_historical_semantics():
    cp, proposal, executor = load()
    for label in (P2_CP, I.CONTROL_PLANE_P4_REVISION):
        refused(cp, proposal, executor, label, "combination")
    # the cp record alone carries the same six members the historical generation accepts: it is labelled historical, not current
    assert run(cp, proposal, None, P2_CP).import_reports[0].adapter_profile == "control-plane-programme2-profiles@7a4bcd40"


def test_mixed_pairs_are_refused_in_both_directions():
    cp, proposal, executor = load()
    historical = copy.deepcopy(executor)
    historical["repository"]["revision"] = P2_RT
    historical["provenance"]["source_asserted"]["repository_revision"] = P2_RT
    refused(cp, proposal, historical, CUR_CP, "combination")  # current Control Plane + historical runtime
    refused(cp, proposal, executor, P2_CP, "combination")  # historical Control Plane + current runtime
    assert run(cp, proposal, historical, P2_CP).import_reports[0].adapter_profile == "control-plane-programme2-profiles@7a4bcd40"


@pytest.mark.parametrize("sha", ["0" * 40, "a" * 40, "b19c47ddd020409d24e52e70b11359c46265edbc", "f7a55e2a8494801e49193f9f46935f0a971c248e"])
def test_an_arbitrary_forty_hex_value_is_refused_for_either_component(sha):
    cp, proposal, executor = load()
    refused(cp, proposal, executor, sha, "unsupported Control Plane revision")
    forged = copy.deepcopy(executor)
    forged["repository"]["revision"] = sha
    forged["provenance"]["source_asserted"]["repository_revision"] = sha
    refused(cp, proposal, forged, CUR_CP, "unsupported Moltbot producer repository revision")


@pytest.mark.parametrize("near", [CUR_CP[:8], CUR_CP[:12], CUR_CP[:39], CUR_CP.upper(), " " + CUR_CP, CUR_CP + " ", CUR_CP + "\n", "latest", "b19c47dd*", ""])
def test_an_abbreviated_uppercase_or_padded_control_plane_label_is_refused(near):
    cp, proposal, executor = load()
    refused(cp, proposal, executor, near, "unsupported Control Plane revision")


@pytest.mark.parametrize("near", [CUR_RT[:8], CUR_RT[:39], CUR_RT.upper(), " " + CUR_RT, CUR_RT + "\n", "latest", "f7a55e2a*"])
def test_an_abbreviated_uppercase_or_padded_runtime_revision_is_refused(near):
    cp, proposal, executor = load()
    forged = copy.deepcopy(executor)
    forged["repository"]["revision"] = near
    forged["provenance"]["source_asserted"]["repository_revision"] = near
    refused(cp, proposal, forged, CUR_CP, "unsupported Moltbot producer repository revision")


def test_a_runtime_export_whose_two_revision_assertions_disagree_is_refused():
    cp, proposal, executor = load()
    forged = copy.deepcopy(executor)
    forged["provenance"]["source_asserted"]["repository_revision"] = P2_RT
    refused(cp, proposal, forged, CUR_CP, "contradicts repository assertion")


def test_runtime_profile_version_1_0_0_is_refused():
    cp, proposal, executor = load()
    forged = copy.deepcopy(executor)
    forged["producer_profile"]["profile_version"] = "1.0.0"
    refused(cp, proposal, forged)
    forged = copy.deepcopy(executor)
    forged["provenance"]["source_asserted"]["producer_profile_version"] = "1.0.0"
    refused(cp, proposal, forged)


def test_a_runtime_export_without_repository_revision_is_refused():
    cp, proposal, executor = load()
    forged = copy.deepcopy(executor)
    del forged["repository"]["revision"]
    refused(cp, proposal, forged)


# ------------------------------------------------------------------------------------------------ the runtime_authority member set
def test_an_unknown_extra_runtime_authority_member_is_refused():
    cp, proposal, executor = load()
    for member in ("x_extra", "tenant_id"):
        forged = copy.deepcopy(cp)
        for a in authority(forged):
            a[member] = "1"
        refused(forged, proposal, executor, match="runtime authority fields unsupported")


@pytest.mark.parametrize("field", ["profile", "catalogue_digest", "approval_commitment", "required_inputs_digest",
                                   "expected_effective_grant_digest", "effective_grant_derivation_version"])
def test_a_missing_runtime_authority_member_is_refused(field):
    cp, proposal, executor = load()
    for a in authority(cp):
        del a[field]
    refused(cp, proposal, executor, match="runtime authority fields unsupported|runtime authority binding missing")


def test_a_malformed_commitment_is_refused():
    cp, proposal, executor = load()
    for a in authority(cp):
        a["catalogue_digest"] = "sha256:zz"
    refused(cp, proposal, executor, match="runtime authority commitment invalid")


# ------------------------------------------------------------------------------------------------ explicit unsupported scope
@pytest.mark.parametrize("label", [CUR_CP, P2_CP, I.CONTROL_PLANE_P4_REVISION])
def test_effective_configuration_is_refused_under_the_current_and_historical_labels(label):
    cp, proposal, executor = load()
    for a in authority(cp):
        a["effective_configuration"] = copy.deepcopy(EFFECTIVE_CONFIGURATION)
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported") as caught:
        run(cp, proposal, None, label)
    assert caught.value.code == "undeclared_member"
    with pytest.raises(ImportContractError):
        run(cp, proposal, executor if label == CUR_CP else None, label)


@pytest.mark.parametrize("members", [{"approval_commitment_version": POLICY_BINDING["approval_commitment_version"]},
                                     {"policy_generation": 1}, {"policy_activation_ref": POLICY_BINDING["policy_activation_ref"]}, POLICY_BINDING])
def test_policy_binding_members_are_refused(members):
    cp, proposal, executor = load()
    for a in authority(cp):
        a.update(members)
    with pytest.raises(ImportContractError, match="runtime authority fields unsupported") as caught:
        run(cp, proposal, executor)
    assert caught.value.code == "undeclared_member"


def test_reason_vocabulary_label_0_3_is_refused():
    cp, proposal, executor = load()
    forged = copy.deepcopy(cp)
    forged["decisions"][0]["reason_vocabulary_version"] = LABEL_03
    refused(forged, proposal, executor)
    revoked_cp, revoked_proposal, revoked_executor = load("revoked")
    for holder in (revoked_cp["refusals"][0], revoked_executor["control_plane_evidence"]["refusal"]):
        holder["reason_vocabulary_version"] = LABEL_03
    refused(revoked_cp, revoked_proposal, revoked_executor)
    only_cp = copy.deepcopy(revoked_cp)
    only_cp["decisions"][0]["reason_vocabulary_version"] = LABEL_03
    refused(only_cp, revoked_proposal, None)


def test_selection_refusal_and_authorization_pin_evidence_are_refused():
    cp, proposal, executor = load("revoked")
    for member in ("selection_refusal", "authorization_pin"):
        forged = copy.deepcopy(executor)
        forged["control_plane_evidence"][member] = {"version": "0.1"}
        forged["execution_result"]["control_plane_evidence"][member] = {"version": "0.1"}
        refused(cp, proposal, forged)
