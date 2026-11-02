"""RW-01-F4-PoC F-1: the explicit F4 structural selector ``REGISTRY_AUTHENTICATED_SELECTION_F4_PROFILE`` over a REAL Control Plane ``GovernedAgeWorkflow`` record.

The fixtures under ``fixtures/rw01_f4_governed_real/`` are UNEDITED run records produced by the real Control Plane #102 head (see PROVENANCE.md there) and persisted/retrieved
through its own ``BoundedRecordStore``. Only the VERIFIER is a stub here (Replay-unit scope: Replay holds no cryptography; real Ed25519 is exercised in the qualification
battery). The stub is pinned to the genuine texts of the fixture, so a changed text is refused by the stub exactly as a signature failure would be, and the stub's verdict
carries the record's own f4_ages digest/values (a stub proves nothing about authentication; NF-2).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from agent_replay_bundle import (REGISTRY_AUTHENTICATED_SELECTION_F4_PROFILE, REGISTRY_AUTHENTICATED_SELECTION_PROFILE, ImportContractError)
from agent_replay_bundle import importers as I
from agent_replay_bundle.registry_evidence import RegistryEvidenceTrust, RegistryExpectedContext, RegistryTrustSnapshotRef
from tests import rw01_f4_support as S

FIX = Path(__file__).parent / "fixtures" / "rw01_f4_governed_real"
F4 = REGISTRY_AUTHENTICATED_SELECTION_F4_PROFILE
CUR = I.CONTROL_PLANE_CUR_REVISION
# Operator-side values (independent of the record; they are the values the producer's scope/clock were configured with)
CTX = dict(consumer_id="consumer-test", tenant="tenant-alpha", institution="urn:cognous:institution:synthetic-customer-service", authority_domain="customer-refunds",
           operation="refund-issue-routine")
ACTION = "urn:cognous:action:refund-issue-routine-v1"
HOST = {"status_max_age_seconds": 60, "approval_max_age_seconds": 60}


def _load(sub=""):
    d = FIX / sub if sub else FIX
    return json.loads((d / "run.json").read_text()), json.loads((d / "proposal.json").read_text())


REAL, PROPOSAL = _load()
REFUSAL, REFUSAL_PROPOSAL = _load("effect_refusal")
HOLD, HOLD_PROPOSAL = _load("hold_only")


def _dec(cp):
    return cp["decisions"][0]


def _verifier(cp=REAL, extra=None, **kw):
    ev = _dec(cp)["selection_evidence"]
    ec = _dec(cp)["binding"]["runtime_authority"]["effective_configuration"]["members"]
    row = next(r for r in ec["families"] if r["slot"] == "f4_ages")

    def mutate(verdict, request):
        verdict["effective_policy_digest"] = row["effective_policy_digest"]
        verdict["effective_values"] = dict(ec["f4_scalars"])
        if extra is not None:
            extra(verdict, request)

    return S.LogicOnlyStubVerifier(genuine={ev["selection_text"]: (ev["record_text"], {k: 600 for k in S.AGES}, "issuer-test-1", "sel-real", 1)}, mutate=mutate, **kw)


def _trust(cp=REAL, **over):
    kw = dict(verifier=over.pop("verifier", None) or _verifier(cp if "selection_evidence" in _dec(cp) else REAL), trust_snapshot=S.OpaqueSnapshot(), trust_snapshot_ref=RegistryTrustSnapshotRef(snapshot_id="snap-1", version=7),
              expected_context=RegistryExpectedContext(**CTX), expected_action_id=ACTION, expected_operation_id=CTX["operation"], verification_time=S.T0, time_mode="as_of",
              min_trust_snapshot_version=5, last_accepted_snapshot=(7, "fp-7"), expected_host_ages=dict(HOST), control_plane_source_revision=S.CP_REV,
              registry_source_revision=S.REG_REV)
    kw.update(over)
    return RegistryEvidenceTrust(**kw)


def _import(cp=REAL, proposal=PROPOSAL, trust=None, selector=F4, **kw):
    trust = _trust(cp) if trust is None else trust
    return I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=kw.pop("revision", CUR),
                                     control_plane_profile=selector, registry_evidence_trust=trust, **kw)


def _refused(code, cp, proposal=PROPOSAL, **kw):
    with pytest.raises(ImportContractError) as exc:
        _import(cp, proposal, **kw)
    assert exc.value.code == code, (exc.value.code, str(exc.value))
    return exc.value


def _mutated(fn, base=REAL):
    cp = copy.deepcopy(base)
    fn(cp)
    return cp


def test_control_positive_real_record_imports_and_is_unchanged():
    trust = _trust()
    bundle = _import(trust=trust)
    assert len(trust.verifier.calls) == 1
    md = bundle.metadata
    assert md["control_plane_profile"] == F4
    assert md["registry_authenticated"] is False
    assert md["registry_authentication_claim"] == "A_selection_signature_per_injected_verifier"
    assert md["control_plane_decision_authenticated"] is False
    assert md["registry_origin"] == "registry_origin_unverified"
    assert [k for k in md if k.startswith(("claim_b", "decision_authentic", "registry_origin_verified"))] == []
    # the retained decision is byte-identical to the persisted one (nothing grafted, re-sealed or inferred)
    (rec,) = [r for r in bundle.records if r.record_type == "runtime_decision"]
    assert json.dumps(rec.data, sort_keys=True) == json.dumps(_dec(REAL), sort_keys=True)
    assert rec.data["selection_evidence"] == _dec(REAL)["selection_evidence"]
    for member in ("reason_vocabulary_version", "rule_identity", "reopen_conditions", "evaluated_at", "recorded_at"):
        assert member not in rec.data
    assert set(rec.data["binding"]["runtime_authority"]) == {"effective_configuration"}
    assert not any(r.record_type in ("resolution_check_event",) for r in bundle.records)


def test_record_with_effect_time_refusal_row_imports():
    assert REFUSAL["refusals"], "fixture must carry a real effect-time refusal row"
    assert "reason_vocabulary_version" not in REFUSAL["refusals"][0]
    trust = _trust(REFUSAL)
    bundle = _import(REFUSAL, REFUSAL_PROPOSAL, trust)
    assert len(trust.verifier.calls) == 1 and bundle.metadata["registry_authenticated"] is False
    assert any(r.record_type == "runtime_refusal" or "refusal" in r.record_type for r in bundle.records)


def test_old_selector_on_the_same_record_is_still_refused_as_before():
    _import()  # control positive: the F4 selector admits this record
    for selector, trust in ((REGISTRY_AUTHENTICATED_SELECTION_PROFILE, _trust()), (S.OLD_SELECTOR, None), (None, None)):
        kw = {} if trust is None else {"registry_evidence_trust": trust}
        with pytest.raises(ImportContractError) as exc:
            I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=CUR, control_plane_profile=selector, **kw)
        assert "resolution journal missing" in str(exc.value) and exc.value.code is None


@pytest.mark.parametrize("name,mutate,code", [
    ("check_events added", lambda c: c.__setitem__("check_events", [{"x": 1}]), "undeclared_member"),
    ("vocabulary_changes added", lambda c: c.__setitem__("vocabulary_changes", [{"x": 1}]), "undeclared_member"),
    ("reason_vocabulary_version added", lambda c: _dec(c).__setitem__("reason_vocabulary_version", "runtime-authority-reasons/0.1"), "undeclared_member"),
    ("rule_identity added", lambda c: _dec(c).__setitem__("rule_identity", "r"), "undeclared_member"),
    ("reopen_conditions added", lambda c: _dec(c).__setitem__("reopen_conditions", []), "undeclared_member"),
    ("approval_commitment added", lambda c: _dec(c)["binding"]["runtime_authority"].__setitem__("approval_commitment", "sha256:" + "0" * 64), "undeclared_member"),
    ("profile member added", lambda c: _dec(c)["binding"]["runtime_authority"].__setitem__("profile", "runtime-authority/0.1"), "undeclared_member"),
    ("arbitrary extra runtime_authority member", lambda c: _dec(c)["binding"]["runtime_authority"].__setitem__("zzz", 1), "undeclared_member"),
    ("check_events present-but-empty", lambda c: c.__setitem__("check_events", []), "undeclared_member"),
    ("vocabulary_changes present-but-empty", lambda c: c.__setitem__("vocabulary_changes", []), "undeclared_member"),
    ("programme-2 ledger present-but-empty (operations)", lambda c: c.__setitem__("operations", []), "undeclared_member"),
    ("programme-2 ledger present-but-empty (rule_revisions)", lambda c: c.__setitem__("rule_revisions", []), "undeclared_member"),
    ("programme-2 ledger present-but-empty (age_extensions)", lambda c: c.__setitem__("age_extensions", []), "undeclared_member"),
    ("freshness activation via decision evaluated_at", lambda c: _dec(c).__setitem__("evaluated_at", "2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("freshness activation via attempt evaluated_at", lambda c: c["attempts"][0].__setitem__("evaluated_at", "2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("decision recorded_at", lambda c: _dec(c).__setitem__("recorded_at", "2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("attempt recorded_at", lambda c: c["attempts"][0].__setitem__("recorded_at", "2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("decision deadline", lambda c: _dec(c).__setitem__("deadline", "2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("decision age_bound_seconds", lambda c: _dec(c).__setitem__("age_bound_seconds", 5), "undeclared_member"),
    ("decision approval_commitment", lambda c: _dec(c).__setitem__("approval_commitment", "sha256:" + "0" * 64), "undeclared_member"),
    ("decision check_id", lambda c: _dec(c).__setitem__("check_id", "x"), "undeclared_member"),
    ("decision check_events", lambda c: _dec(c).__setitem__("check_events", []), "undeclared_member"),
    ("binding rule_identity", lambda c: _dec(c)["binding"].__setitem__("rule_identity", "r"), "undeclared_member"),
    ("binding reason_vocabulary_version", lambda c: _dec(c)["binding"].__setitem__("reason_vocabulary_version", "runtime-authority-reasons/0.1"), "undeclared_member"),
    ("binding reopen_conditions", lambda c: _dec(c)["binding"].__setitem__("reopen_conditions", []), "undeclared_member"),
    ("binding check_events", lambda c: _dec(c)["binding"].__setitem__("check_events", []), "undeclared_member"),
    ("attempt rule_identity", lambda c: c["attempts"][0].__setitem__("rule_identity", "r"), "undeclared_member"),
    ("selection_evidence removed", lambda c: _dec(c).pop("selection_evidence"), "selection_evidence_missing"),
])
def test_structural_and_admission_refusals_are_typed_and_caused_by_the_mutation(name, mutate, code):
    assert _import() is not None  # control positive in the same test: the unmutated record imports
    trust = _trust()
    exc = _refused(code, _mutated(mutate), trust=trust)
    if code == "undeclared_member":
        assert len(trust.verifier.calls) == 0  # structural refusal precedes admission
    assert exc.code == code


def test_tampered_binding_tenant_is_refused_by_the_effective_configuration_check():
    assert _import() is not None
    cp = _mutated(lambda c: _dec(c)["binding"].__setitem__("tenant_id", "tenant-x"))
    with pytest.raises(ImportContractError) as exc:
        _import(cp)
    assert exc.value.code == "schema_violation" and "tenant" in str(exc.value)


def test_tampered_selection_text_is_refused_by_the_verifier_and_names_the_layer():
    assert _import() is not None
    cp = _mutated(lambda c: _dec(c)["selection_evidence"].__setitem__("selection_text", _dec(c)["selection_evidence"]["selection_text"].replace("tenant-alpha", "tenant-beta")))
    trust = _trust(REAL)
    _refused("registry_evidence_unverified:signature_invalid", cp, trust=trust)
    assert len(trust.verifier.calls) == 1


def test_tampered_verdict_echo_is_refused():
    # a verifier that answers for other texts than the ones Replay sent (echo check)
    assert _import() is not None
    trust = _trust(verifier=_verifier(extra=lambda v, req: v.__setitem__("selection_text_sha256", "0" * 64)))
    _refused("registry_evidence_input_echo_mismatch", REAL, trust=trust)


def test_wrong_operator_tenant_is_refused_before_the_verifier_is_called():
    assert _import() is not None
    trust = _trust(expected_context=RegistryExpectedContext(**{**CTX, "tenant": "tenant-other"}))
    _refused("registry_evidence_scope_mismatch", REAL, trust=trust)
    assert len(trust.verifier.calls) == 0


def test_hold_only_record_is_selection_evidence_missing():
    assert _import() is not None
    assert _dec(HOLD)["result"] == "hold" and "selection_evidence" not in _dec(HOLD)
    _refused("selection_evidence_missing", HOLD, HOLD_PROPOSAL, trust=_trust(HOLD))


def test_selector_misuse_is_refused_like_the_existing_selector():
    assert _import() is not None
    # trust required (no structural-only fallback)
    with pytest.raises(ImportContractError) as exc:
        I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=CUR, control_plane_profile=F4)
    assert exc.value.code == "registry_evidence_trust_missing"
    # conflicting mode with the caller-trusted expected digest
    ec = _dec(REAL)["binding"]["runtime_authority"]["effective_configuration"]["digest"]
    with pytest.raises(ImportContractError) as exc:
        _import(expected_effective_configuration_digest=ec)
    assert exc.value.code == "registry_evidence_conflicting_modes"
    # non-current revisions are refused (selector is unsupported there), never silently downgraded
    for rev in (I.CONTROL_PLANE_REVISION, *sorted(set(I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS) - {CUR})):
        with pytest.raises(ImportContractError) as exc:
            _import(revision=rev)
        assert str(exc.value) == "unsupported Control Plane profile selector", rev
    # exact str match only
    class Str(str):
        pass
    for bad in (Str(F4), F4 + " ", F4.upper(), "registry-authenticated-selection-f4-governed/0.2", "registry-authenticated-selection-f4-governed"):
        with pytest.raises(ImportContractError) as exc:
            _import(selector=bad)
        assert str(exc.value) == "unsupported Control Plane profile selector"
    # trust keyword without any selector
    with pytest.raises(ImportContractError) as exc:
        I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=CUR, registry_evidence_trust=_trust())
    assert exc.value.code == "registry_evidence_unsupported_profile"


def test_selection_evidence_is_still_refused_under_every_other_selector_and_revision():
    assert _import() is not None  # control positive: it is admitted only under the F4 selector on CUR
    revisions = (I.CONTROL_PLANE_REVISION, *sorted(set(I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS)))
    for rev in revisions:
        for selector in (None, S.OLD_SELECTOR, REGISTRY_AUTHENTICATED_SELECTION_PROFILE):
            kw = {}
            if selector == REGISTRY_AUTHENTICATED_SELECTION_PROFILE and rev == CUR:
                kw["registry_evidence_trust"] = _trust()
            if selector in (S.OLD_SELECTOR, REGISTRY_AUTHENTICATED_SELECTION_PROFILE) and rev != CUR:
                with pytest.raises(ImportContractError) as exc:
                    I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=rev, control_plane_profile=selector, **kw)
                assert str(exc.value) == "unsupported Control Plane profile selector", (rev, selector)
                continue
            # the structural check or the named-key guard refuses first; the cause is asserted, and the guard itself is pinned below
            with pytest.raises(ImportContractError) as exc:
                I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=rev, control_plane_profile=selector, **kw)
            assert any(m in str(exc.value) for m in ("resolution journal missing", "runtime authority fields unsupported", "selection_evidence is admitted only",
                                                     "unsupported", "missing")), (rev, selector, str(exc.value))
            assert exc.value.code in (None, "undeclared_member"), (rev, selector, exc.value.code)


def test_named_key_guard_cause_for_selection_evidence_outside_the_authenticated_profiles():
    # a structurally valid legacy-shaped record carrying selection_evidence: the NAMED-KEY GUARD (not a structural check) is the cause
    cp, proposal = S.f4_run()
    assert _import(cp, proposal, trust=S.make_trust(), selector=S.SELECTOR) is not None
    with pytest.raises(ImportContractError) as exc:  # plain current profile: the closed runtime_authority member set refuses first
        I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CUR)
    assert exc.value.code == "undeclared_member" and "runtime authority fields unsupported" in str(exc.value)
    with pytest.raises(ImportContractError) as exc:  # governed (older) selector admits effective_configuration, so the named-key guard is the cause
        I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CUR, control_plane_profile=S.OLD_SELECTOR)
    assert exc.value.code == "undeclared_member" and "selection_evidence is admitted only under the authenticated-selection profile" in str(exc.value)


def test_reverify_retained_registry_evidence_refuses_an_f4_bundle_fail_closed():
    from agent_replay_bundle.registry_evidence import reverify_retained_registry_evidence
    bundle = _import()
    assert bundle.metadata["control_plane_profile"] == F4
    with pytest.raises(ImportContractError):
        reverify_retained_registry_evidence(bundle, registry_evidence_trust=_trust(), proposal=copy.deepcopy(PROPOSAL))


def test_presence_of_selection_evidence_never_selects_the_f4_profile():
    # a record carrying evidence under the plain current profile fails exactly as before (journal missing comes first)
    with pytest.raises(ImportContractError) as exc:
        I.import_bounded_workflow(copy.deepcopy(REAL), proposal=copy.deepcopy(PROPOSAL), control_plane_revision=CUR)
    assert "resolution journal missing" in str(exc.value)


def test_default_path_is_unchanged_and_all_real_fixtures_still_import_under_the_f4_selector():
    # behavioural: the legacy path still refuses the real record at the journal check; the F4 path imports each of the three real fixtures
    for cp, proposal in ((REAL, PROPOSAL), (REFUSAL, REFUSAL_PROPOSAL)):
        with pytest.raises(ImportContractError) as exc:
            I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), control_plane_revision=CUR)
        if cp is REAL:
            assert "resolution journal missing" in str(exc.value) and exc.value.code is None
        assert _import(cp, proposal, _trust(cp)) is not None
    # the hold-only fixture is refused for want of evidence, not for structure
    _refused("selection_evidence_missing", HOLD, HOLD_PROPOSAL, trust=_trust(HOLD))
