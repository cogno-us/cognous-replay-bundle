from __future__ import annotations

import copy

import pytest

from agent_replay_bundle.importers import (
    ImportContractError,
    import_bounded_workflow,
    import_legacy_control_plane_replay,
)
from agent_replay_bundle.reconstruction import (
    redact_reconstruction_bundle,
    sign_reconstruction_bundle,
    verify_reconstruction_hmac,
)


def legacy_source():
    return {
        "replay_bundle_id": "legacy-bundle-1",
        "run_id": "run-1",
        "generated_at": "2026-10-05T00:00:00Z",
        "frame": {
            "frame_id": "frame-1",
            "task": "synthetic",
            "actor": "agent",
            "environment": "test",
            "allowed_tools": [],
            "blocked_tools": [],
            "policy_version": "v1",
            "created_at": "2026-10-05T00:00:00Z",
        },
        "actions": [{
            "action_id": "a1", "run_id": "run-1", "tool_name": "t",
            "action_type": "write", "target": "x", "payload": {},
            "proposed_at": "2026-10-05T00:00:01Z", "reason": None,
        }],
        "decisions": [{
            "decision_id": "d1", "action_id": "a1", "run_id": "run-1",
            "result": "allow", "policy_name": "p", "reason": "ok",
            "decided_at": "2026-10-05T00:00:02Z",
            "deterministic_fingerprint": "fp", "trace_id": None,
        }],
        "policy_traces": [],
        "authority_records": [],
        "reliance_records": [],
        "blocked_actions": [],
        "final_output": None,
    }


def _binding():
    return {
        "proposal_commitment": "placeholder",
        "manifest_id": "m1",
        "manifest_version": "1.1",
        "manifest_digest": "sha256:" + "2" * 64,
        "actor": "actor",
        "principal": "principal",
        "action_id": "refund.issue",
        "adapter_id": "adapter",
        "target": "target",
        "payload_commitment": "sha256:" + "3" * 64,
        "requested_permissions": ["refund.issue"],
        "amount": 50.0,
        "unit": "USD",
        "effects": 1,
        "authority_context_id": "urn:context:instance",
        "authority_context_version": "0.1.0",
        "authority_context_status": "proposed_pending_governor_review",
        "requirement_id": "req-1",
        "requirement_commitment": "sha256:" + "4" * 64,
        "grant_id": "grant-1",
        "grant_revision": "1",
        "policy_versions": [{"ref": "policy", "version": "1"}],
        "role_mapping_version": "roles-v1",
        "role_mapping_digest": "sha256:" + "5" * 64,
        "effective_max_effects": 1,
    }


def _effect_id(binding):
    from agent_replay_bundle.importers import _sha256

    return _sha256({
        "proposal": binding["proposal_commitment"],
        "grant_id": binding["grant_id"],
        "grant_revision": binding["grant_revision"],
    })


def bounded_source():
    from agent_replay_bundle.importers import _sha256

    binding = _binding()
    binding["proposal_commitment"] = _sha256(proposal_source())
    binding["payload_commitment"] = proposal_source()["payload_commitment"]
    effect_id = _effect_id(binding)
    return {
        "run_id": "run-1",
        "decisions": [{
            "decision_id": "decision-1",
            "effect_id": effect_id,
            "result": "authorized",
            "reasons": [],
            "decided_at": "2026-10-05T00:00:00Z",
            "binding": binding,
        }],
        "attempts": [
            {
                "attempt_id": "cp-attempt-1",
                "effect_id": effect_id,
                "decision_id": "decision-1",
                "started_at": "2026-10-05T00:00:01Z",
                "status": "attempted",
                "acknowledgement": {},
                "error": None,
            },
            {
                "attempt_id": "cp-attempt-1",
                "effect_id": effect_id,
                "decision_id": "decision-1",
                "started_at": "2026-10-05T00:00:01Z",
                "status": "unknown",
                "acknowledgement": {},
                "error": "ack lost",
            },
        ],
        "observations": [{
            "effect_id": effect_id,
            "observed_at": "2026-10-05T00:00:02Z",
            "state": "applied",
            "destination_state": {"effect_id": effect_id, "grant_id": "grant-1", "target": "target", "amount": 50.0,
                                  "unit": "USD", "payload": {"customer_id": "c1"}},
        }],
        "reconciliations": [],
    }


def proposal_source():
    from agent_replay_bundle.importers import _sha256

    payload = {"customer_id": "c1"}
    return {
        "manifest_id": "m1",
        "manifest_version": "1.1",
        "manifest_digest": "sha256:" + "2" * 64,
        "actor": "actor",
        "principal": "principal",
        "action_id": "refund.issue",
        "adapter_id": "adapter",
        "target": "target",
        "payload": payload,
        "payload_commitment": _sha256(payload),
        "requested_permissions": ["refund.issue"],
        "amount": 50.0,
        "unit": "USD",
        "effects": 1,
        "authority_context_ref": "urn:profile:0.1.0",
        "requirement_id": "req-1",
        "correlation_id": "corr-1",
        "run_id": "run-1",
        "evidence_refs": ["evidence-1"],
    }


def moltbot_source(cp):
    from agent_replay_bundle.importers import _sha256

    effect_id = cp["decisions"][0]["effect_id"]
    payload = {"customer_id": "c1"}
    op = {
        "actor": "actor",
        "principal": "principal",
        "institution_id": "institution",
        "authority_domain": "customer-refunds",
        "manifest_id": "m1",
        "manifest_version": "1.1",
        "manifest_digest": "sha256:" + "2" * 64,
        "proposal_commitment": cp["decisions"][0]["binding"]["proposal_commitment"],
        "action_id": "refund.issue",
        "adapter_id": "adapter",
        "target": "target",
        "payload": payload,
        "payload_commitment": _sha256(payload),
        "requested_permissions": ["refund.issue"],
        "amount": 50.0,
        "unit": "USD",
        "effects": 1,
        "authority_context_id": "urn:profile:0.1.0",
        "requirement_id": "req-1",
        "grant_id": "grant-1",
        "grant_revision": "1",
        "effective_max_effects": 1,
    }
    operation_digest = _sha256(op)
    return {
        "execution_envelope": {
            "version": "0.2.0",
            "decision_id": "decision-1",
            "effect_id": effect_id,
            "operation": op,
            "attempt_id": None,
        },
        "execution_result": {
            "status": "unknown",
            "decision_id": "decision-1",
            "effect_id": effect_id,
            "attempt_id": "molt-attempt-1",
            "attempted": True,
            "acknowledged": False,
            "observed_state": "applied",
            "newly_executed": True,
            "observation": {"effect_id": effect_id, "state": "applied"},
            "error": "ack lost",
        },
        "attempts": [{
            "attempt_id": "molt-attempt-1",
            "effect_id": effect_id,
            "decision_id": "decision-1",
            "operation_digest": operation_digest,
            "created_at": 1.0,
        }],
        "attempt_events": [
            {"event_id": 1, "attempt_id": "molt-attempt-1", "status": "attempted", "error": None, "created_at": 1.0},
            {"event_id": 2, "attempt_id": "molt-attempt-1", "status": "unknown", "error": "ack lost", "created_at": 2.0},
        ],
        "effects": [{
            "effect_id": effect_id,
            "operation_digest": operation_digest,
            "grant_id": "grant-1",
            "target": "target",
            "amount": 50.0,
            "unit": "USD",
            "payload_json": '{"customer_id":"c1"}',
            "state": "applied",
        }],
    }


def test_confirmed_legacy_mappings_are_explicit():
    bundle = import_legacy_control_plane_replay(legacy_source())
    report = bundle.import_reports[0]
    assert bundle.metadata["source_bundle_id"] == "legacy-bundle-1"
    assert report.field_mappings["actions"] == "records[action_proposal]"
    assert report.field_mappings["decisions"] == "records[policy_decision]"
    assert any(r.record_type == "action_proposal" for r in bundle.records)
    assert any(r.record_type == "policy_decision" for r in bundle.records)


def test_bounded_lifecycle_transitions_are_not_collapsed():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    transitions = [r for r in bundle.records if r.record_type == "control_plane_attempt_transition"]
    assert [r.data["status"] for r in transitions] == ["attempted", "unknown"]
    assert transitions[0].identifiers["attempt_id"] == transitions[1].identifiers["attempt_id"]
    assert bundle.semantics.external_effect_execution is False


def test_unknown_ack_followed_by_applied_observation_is_preserved():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    statuses = [r.data["status"] for r in bundle.records if r.record_type == "control_plane_attempt_transition"]
    observations = [r.data["state"] for r in bundle.records if r.record_type == "effect_observation"]
    assert statuses[-1] == "unknown"
    assert observations[-1] == "applied"


def test_separate_attempt_namespaces_are_not_equated_without_explicit_link():
    cp = bounded_source()
    bundle = import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=moltbot_source(cp))
    assert bundle.links == []
    finding = next(f for f in bundle.import_reports[0].findings if f.code == "M002")
    assert finding.value_state == "unknown"


def test_explicit_executor_attempt_link_is_preserved_without_identity_equivalence():
    cp = bounded_source()
    cp["attempts"][-1]["acknowledgement"] = {"attempt_id": "molt-attempt-1"}
    bundle = import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=moltbot_source(cp))
    assert len(bundle.links) == 1
    assert bundle.links[0].link_type == "explicit"
    assert bundle.links[0].establishes_identity_equivalence is False


def test_conflicting_immutable_attempt_content_is_rejected():
    cp = bounded_source()
    cp["attempts"][1]["started_at"] = "2026-10-05T00:00:09Z"
    with pytest.raises(ImportContractError, match="conflicting content"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_conflicting_immutable_effect_content_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    second = copy.deepcopy(m["effects"][0])
    second["target"] = "different"
    m["effects"].append(second)
    with pytest.raises(ImportContractError, match="target conflicts|conflicting content"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_dangling_control_plane_decision_reference_is_rejected():
    cp = bounded_source()
    cp["attempts"][0]["decision_id"] = "missing"
    with pytest.raises(ImportContractError, match="dangling decision_id"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_dangling_control_plane_effect_reference_is_rejected():
    cp = bounded_source()
    cp["observations"][0]["effect_id"] = "missing"
    with pytest.raises(ImportContractError, match="dangling effect_id"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_dangling_moltbot_attempt_event_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["attempt_events"][0]["attempt_id"] = "missing"
    with pytest.raises(ImportContractError, match="dangling"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_moltbot_operation_digest_tamper_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["effects"][0]["operation_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ImportContractError, match="operation_digest mismatch"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_moltbot_identifier_mismatch_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["execution_result"]["effect_id"] = "wrong"
    with pytest.raises(ImportContractError, match="identifiers"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_unsupported_executor_version_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["execution_envelope"]["version"] = "9.9.9"
    with pytest.raises(ImportContractError, match="unsupported"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_effect_identity_tamper_is_rejected():
    cp = bounded_source()
    cp["decisions"][0]["effect_id"] = "sha256:" + "0" * 64
    with pytest.raises(ImportContractError, match="effect identity"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_payload_commitment_tamper_is_rejected():
    p = proposal_source()
    p["payload"]["customer_id"] = "tampered"
    with pytest.raises(ImportContractError, match="payload commitment"):
        import_bounded_workflow(bounded_source(), proposal=p)


def test_hmac_detects_tamper_and_is_shared_secret_only():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    signed = sign_reconstruction_bundle(bundle, "secret", key_id="test-key")
    assert verify_reconstruction_hmac(signed, "secret") is True
    assert verify_reconstruction_hmac(signed, "wrong") is False
    signed.records[0].data["actor"] = "tampered"
    assert verify_reconstruction_hmac(signed, "secret") is False
    hmac_metadata = next(i for i in signed.integrity if i.kind == "hmac")
    assert "shared secret" in hmac_metadata.verification_claim


def test_redaction_creates_new_derivative_identity_and_drops_stale_hmac():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    signed = sign_reconstruction_bundle(bundle, "secret")
    target = next(r.source_path for r in signed.records if r.record_type == "runtime_proposal")
    redacted = redact_reconstruction_bundle(signed, redact_paths={target})
    assert redacted.bundle_id != signed.bundle_id
    assert redacted.derivation.source_bundle_id == signed.bundle_id
    assert redacted.status == "redacted"
    assert all(i.kind != "hmac" for i in redacted.integrity)
    assert any(i.kind == "content-digest" for i in redacted.integrity)
    assert verify_reconstruction_hmac(redacted, "secret") is False
    assert any(f.value_state == "redacted" for f in redacted.import_reports[0].findings)


def test_governor_regression_proposal_actor_mismatch_is_rejected():
    cp = bounded_source()
    p = proposal_source()
    p["actor"] = "urn:attacker"
    with pytest.raises(ImportContractError, match="proposal_commitment|actor"):
        import_bounded_workflow(cp, proposal=p, moltbot_export=moltbot_source(cp))


def test_governor_regression_destination_amount_mismatch_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["effects"][0]["amount"] = 999999
    with pytest.raises(ImportContractError, match="amount conflicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_governor_regression_dangling_execution_result_attempt_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["execution_result"]["attempt_id"] = "nonexistent-attempt"
    with pytest.raises(ImportContractError, match="dangling attempt_id"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_governor_regression_recomputed_attacker_envelope_still_conflicts_with_decision():
    from agent_replay_bundle.importers import _sha256

    cp = bounded_source()
    m = moltbot_source(cp)
    m["execution_envelope"]["operation"]["target"] = "urn:attacker"
    digest = _sha256(m["execution_envelope"]["operation"])
    m["attempts"][0]["operation_digest"] = digest
    m["effects"][0]["operation_digest"] = digest
    m["effects"][0]["target"] = "urn:attacker"
    with pytest.raises(ImportContractError, match="target conflicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_governor_regression_hmac_subject_substitution_fails():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    signed = sign_reconstruction_bundle(bundle, "secret", key_id="test-key")
    hmac_metadata = next(i for i in signed.integrity if i.kind == "hmac")
    hmac_metadata.subject_bundle_id = "different-bundle"
    assert verify_reconstruction_hmac(signed, "secret") is False


def test_hmac_algorithm_profile_key_label_and_claim_substitution_fail():
    bundle = import_bounded_workflow(bounded_source(), proposal=proposal_source())
    for field, value in (
        ("canonicalization_profile", "other-profile"),
        ("key_id", "substituted-key-label"),
        ("verification_claim", "different claim"),
    ):
        signed = sign_reconstruction_bundle(bundle, "secret", key_id="test-key")
        setattr(next(i for i in signed.integrity if i.kind == "hmac"), field, value)
        assert verify_reconstruction_hmac(signed, "secret") is False


def test_destination_payload_mismatch_is_rejected_even_with_matching_digest():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["effects"][0]["payload_json"] = '{"customer_id":"attacker"}'
    with pytest.raises(ImportContractError, match="payload_json conflicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_execution_result_embedded_observation_effect_mismatch_is_rejected():
    cp = bounded_source()
    m = moltbot_source(cp)
    m["execution_result"]["observation"]["effect_id"] = "different"
    with pytest.raises(ImportContractError, match="observation.effect_id"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=m)


def test_reconciliation_embedded_observation_mismatch_is_rejected():
    cp = bounded_source()
    eid = cp["decisions"][0]["effect_id"]
    cp["reconciliations"] = [{
        "effect_id": eid,
        "reconciled_at": "2026-10-05T00:00:03Z",
        "result": "applied",
        "observation": {
            "effect_id": "different",
            "observed_at": "2026-10-05T00:00:03Z",
            "state": "applied",
            "destination_state": {},
        },
    }]
    with pytest.raises(ImportContractError, match="observation.effect_id"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_multiple_bound_decisions_rejected_by_single_proposal_importer():
    cp = bounded_source()
    second = copy.deepcopy(cp["decisions"][0])
    second["decision_id"] = "decision-2"
    cp["decisions"].append(second)
    with pytest.raises(ImportContractError, match="multiple authorization bindings"):
        import_bounded_workflow(cp, proposal=proposal_source())


def test_missing_proposal_with_moltbot_evidence_is_rejected_not_promoted_complete():
    cp = bounded_source()
    with pytest.raises(ImportContractError, match="requires the corresponding RuntimeProposal"):
        import_bounded_workflow(cp, moltbot_export=moltbot_source(cp))


def versioned_moltbot_source(cp):
    from agent_replay_bundle.importers import (
        MOLTBOT_PRODUCER_PROFILE_ID,
        MOLTBOT_PRODUCER_PROFILE_VERSION,
        MOLTBOT_SAFE_REVISION,
    )
    source = moltbot_source(cp)
    source["producer_profile"] = {
        "profile_id": MOLTBOT_PRODUCER_PROFILE_ID,
        "profile_version": MOLTBOT_PRODUCER_PROFILE_VERSION,
        "execution_envelope_version": "0.2.0",
    }
    source["repository"] = {
        "repository": "cogno-us/moltbot-safe",
        "revision": MOLTBOT_SAFE_REVISION,
        "revision_status": "source_asserted",
    }
    source["provenance"] = {
        "source_asserted": {
            "repository_revision": MOLTBOT_SAFE_REVISION,
            "producer_profile_id": MOLTBOT_PRODUCER_PROFILE_ID,
            "producer_profile_version": MOLTBOT_PRODUCER_PROFILE_VERSION,
        },
        "independently_established": [],
        "meaning": "source assertion only",
    }
    observation = copy.deepcopy(source["execution_result"]["observation"])
    observation["destination_state"] = {
        "effect_id": source["execution_envelope"]["effect_id"],
        "grant_id": source["execution_envelope"]["operation"]["grant_id"],
        "target": source["execution_envelope"]["operation"]["target"],
        "amount": source["execution_envelope"]["operation"]["amount"],
        "unit": source["execution_envelope"]["operation"]["unit"],
        "payload": copy.deepcopy(source["execution_envelope"]["operation"]["payload"]),
        "state": "applied",
    }
    source["attempt_identity"] = {
        "namespace": "executor",
        "attempt_id": source["execution_result"]["attempt_id"],
        "owner": "cogno-us/moltbot-safe",
    }
    source["control_plane_attempts"] = []
    source["observations"] = [observation]
    return source


def test_versioned_executor_profile_is_distinct_from_repository_provenance():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    bundle = import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)
    contract = bundle.metadata["moltbot_producer_contract"]
    assert contract["interface_profile_version"] == "1.0.0"
    assert contract["repository_revision"] == source["repository"]["revision"]
    assert contract["provenance"]["source_asserted"]["repository_revision"] == source["repository"]["revision"]
    assert contract["provenance"]["independently_established"] == []
    assert contract["legacy"] is False
    assert any(r.record_type == "executor_observation" for r in bundle.records)


@pytest.mark.parametrize(
    "mutation",
    ["profile_id", "profile_version", "repository_revision", "provenance_revision"],
)
def test_versioned_executor_profile_rejects_unsupported_or_contradictory_contract(mutation):
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    if mutation == "profile_id":
        source["producer_profile"]["profile_id"] = "urn:unsupported"
    elif mutation == "profile_version":
        source["producer_profile"]["profile_version"] = "9.9.9"
    elif mutation == "repository_revision":
        source["repository"]["revision"] = "unsupported"
    else:
        source["provenance"]["source_asserted"]["repository_revision"] = "contradictory"
    with pytest.raises(ImportContractError, match="unsupported|contradicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


def test_legacy_unversioned_executor_export_remains_revision_pinned():
    from agent_replay_bundle.importers import LEGACY_MOLTBOT_SAFE_REVISION

    cp = bounded_source()
    bundle = import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=moltbot_source(cp))
    contract = bundle.metadata["moltbot_producer_contract"]
    assert contract["legacy"] is True
    assert contract["repository_revision"] == LEGACY_MOLTBOT_SAFE_REVISION
    assert contract["interface_profile_version"] is None



def test_versioned_executor_rejects_wrong_attempt_namespace_owner():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["attempt_identity"]["owner"] = "cogno-us/cognous-agent-control-plane"
    with pytest.raises(ImportContractError, match="executor attempt_identity owner mismatch"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


def test_versioned_executor_rejects_dangling_executor_attempt_identity():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["attempt_identity"]["attempt_id"] = "executor-attempt-missing"
    source["execution_result"]["attempt_id"] = "executor-attempt-missing"
    with pytest.raises(ImportContractError, match="dangling attempt_id|dangling executor attempt_id"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


def _versioned_control_plane_reconciliation(cp):
    source = versioned_moltbot_source(cp)
    cp_attempt = copy.deepcopy(cp["attempts"][-1])
    source["execution_result"]["status"] = "reconciled"
    source["execution_result"]["newly_executed"] = False
    source["execution_result"]["attempt_id"] = cp_attempt["attempt_id"]
    source["attempt_identity"] = {
        "namespace": "control_plane",
        "attempt_id": cp_attempt["attempt_id"],
        "owner": "cogno-us/cognous-agent-control-plane",
    }
    source["control_plane_attempts"] = [cp_attempt]
    return source


def test_control_plane_attempt_evidence_requires_exact_owning_run_record():
    cp = bounded_source()
    source = _versioned_control_plane_reconciliation(cp)
    bundle = import_bounded_workflow(
        cp, proposal=proposal_source(), moltbot_export=source
    )
    attributed = [
        r for r in bundle.records
        if r.record_type == "moltbot_attributed_control_plane_attempt"
    ]
    assert len(attributed) == 1
    links = [
        link for link in bundle.links
        if link.from_record_id == attributed[0].record_id
    ]
    assert len(links) == 1
    assert links[0].establishes_identity_equivalence is True


def test_control_plane_attempt_matching_labels_without_full_record_match_is_rejected():
    cp = bounded_source()
    source = _versioned_control_plane_reconciliation(cp)
    source["control_plane_attempts"][0]["status"] = "fabricated-status"
    with pytest.raises(ImportContractError, match="conflicts with owning producer record"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


def test_control_plane_attempt_wrong_namespace_attribution_is_rejected():
    cp = bounded_source()
    source = _versioned_control_plane_reconciliation(cp)
    source["attempt_identity"]["namespace"] = "executor"
    source["attempt_identity"]["owner"] = "cogno-us/moltbot-safe"
    with pytest.raises(ImportContractError, match="dangling attempt_id|dangling executor attempt_id"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


@pytest.mark.parametrize("state", ["absent", "unknown"])
def test_versioned_historical_absence_or_unknown_without_effect_is_supported(state):
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["effects"] = []
    source["attempts"] = []
    source["attempt_events"] = []
    source["attempt_identity"] = None
    source["control_plane_attempts"] = []
    source["execution_result"].update({
        "status": "observed",
        "attempt_id": None,
        "attempted": False,
        "acknowledged": False,
        "observed_state": state,
        "newly_executed": False,
        "observation": {
            "effect_id": source["execution_envelope"]["effect_id"],
            "state": state,
            "destination_state": {},
        },
    })
    source["observations"] = [copy.deepcopy(source["execution_result"]["observation"])]
    bundle = import_bounded_workflow(
        cp, proposal=proposal_source(), moltbot_export=source
    )
    assert any(
        r.record_type == "executor_observation" and r.data["state"] == state
        for r in bundle.records
    )


def test_versioned_denied_no_effect_outcome_is_supported():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["effects"] = []
    source["attempts"] = []
    source["attempt_events"] = []
    source["attempt_identity"] = None
    source["control_plane_attempts"] = []
    source["execution_result"].update({
        "status": "denied",
        "attempt_id": None,
        "attempted": False,
        "acknowledged": False,
        "observed_state": "unknown",
        "newly_executed": False,
        "observation": {},
    })
    source["observations"] = []
    bundle = import_bounded_workflow(
        cp, proposal=proposal_source(), moltbot_export=source
    )
    assert not any(r.record_type == "destination_effect" for r in bundle.records)


def test_versioned_denied_with_effect_is_rejected():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["execution_result"]["status"] = "denied"
    source["execution_result"]["attempt_id"] = None
    source["attempt_identity"] = None
    source["execution_result"]["attempted"] = False
    source["execution_result"]["newly_executed"] = False
    with pytest.raises(ImportContractError, match="denied execution result contradicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


def test_versioned_operation_content_substitution_is_rejected_even_if_attempt_digest_changes():
    cp = bounded_source()
    source = versioned_moltbot_source(cp)
    source["execution_envelope"]["operation"]["amount"] = 999.0
    from agent_replay_bundle.importers import _sha256
    changed = _sha256(source["execution_envelope"]["operation"])
    source["attempts"][0]["operation_digest"] = changed
    source["effects"][0]["operation_digest"] = changed
    source["effects"][0]["amount"] = 999.0
    with pytest.raises(ImportContractError, match="amount conflicts"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)


@pytest.mark.parametrize("location,versioned", [
    ("top_level", True),
    ("top_level", False),  # legacy unversioned exports carry only the top level
    ("producer_profile", True),
    ("repository", True),
])
def test_executor_export_unknown_member_is_rejected_not_dropped(location, versioned):
    """Unsupported fields in typed records reject rather than disappear (F-10, runtime #98)."""
    cp = bounded_source()
    source = versioned_moltbot_source(cp) if versioned else moltbot_source(cp)
    if location == "top_level":
        source["injected_unknown_member"] = "x"
    else:
        source[location]["injected_unknown_member"] = "x"
    with pytest.raises(ImportContractError, match="unsupported member.*injected_unknown_member"):
        import_bounded_workflow(cp, proposal=proposal_source(), moltbot_export=source)
