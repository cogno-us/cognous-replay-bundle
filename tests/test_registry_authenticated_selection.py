"""Registry-authenticated selection profile (``registry-authenticated-selection/0.1``), sprint RW-01-F4-PoC, Replay side (C3 of the frozen contract).

SCOPE OF THESE TESTS (read before relying on a PASS). Every test here drives the real enforcement boundary ``import_bounded_workflow(...)`` (or
``reverify_retained_registry_evidence``) with ``tests/rw01_f4_support.LogicOnlyStubVerifier``: a STUB that compares strings and checks NO signature. They prove the
REPLAY-SIDE logic only: selector/sentinel matrix, trust validation, admission order, the closed verdict gate, echo checks, binding to the Replay record, conservative
markers, typed refusals, retained-bundle re-verification. They make NO cryptographic claim; Replay holds no crypto and cannot tell the stub from a genuine Registry adapter
(NF-2, pinned below). Real-Ed25519 evidence (N01-N08, N12-N15, N19 negative/positive with PyNaCl) belongs to the Registry and Control Plane PRs of this sprint.

Sprint numbering (N01..N28) is used verbatim in names where applicable. Every negative asserts the SPECIFIC typed code AND that nothing was produced (no bundle returned, no
admission marker anywhere in the exception, no stub call where the refusal is meant to precede verification).

Claim scope of every positive: mechanism verified with synthetic keys; Registry-origin authority not established; claim B not made; decision-time only; operator trust
inputs independence unverified.
"""
import ast
import copy
import json
import re
import sys
import types
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError
from agent_replay_bundle import effective_configuration as EC
from agent_replay_bundle import importers as I
from agent_replay_bundle import reconstruction as RC
from agent_replay_bundle import registry_evidence as RE
from agent_replay_bundle.registry_evidence import RegistryEvidenceTrust, RegistryExpectedContext, RegistryTrustSnapshotRef, reverify_retained_registry_evidence

from . import rw01_f4_support as S
from .rw01_f4_support import (ACTION, ALT_RECORD, ALT_SELECTION, CP_REV, CTX, HOST, LAYERS, OPERATION, RECORD, RECORD_NONASCII, REG_REV, SELECTION, SELECTION_NONASCII,
                              SELECTOR, SNAPSHOT_SECRET, T0, VERIFIER_SECRET, LogicOnlyStubVerifier, do_import, evidence, f4_run, make_trust, raw_trust, reseal_members)

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "agent_replay_bundle"
SUCCESS_ONLY = RE.SUCCESS_MARKER_KEYS - {"control_plane_profile", "effective_configuration_verification", "registry_authenticated", "registry_origin"}
FORBIDDEN_IN_FAILURE = ("admitted_by_operator_supplied_verifier", "registry_selection_admitted_by_injected_verifier", SNAPSHOT_SECRET, VERIFIER_SECRET)


def refused(cp, proposal, code, *, calls=None, **kw):
    """The import must raise ``ImportContractError`` with exactly ``code``; nothing is returned and the message carries no marker, snapshot or verifier text.
    ``calls`` (when given) is the expected number of verifier invocations."""
    trust = kw.get("trust")
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = do_import(cp, proposal, **kw)
    assert result is None
    assert caught.value.code == code, (caught.value.code, str(caught.value))
    text = str(caught.value) + repr(caught.value.args)
    assert not any(secret in text for secret in FORBIDDEN_IN_FAILURE)
    if calls is not None:
        assert len(trust.verifier.calls) == calls
    return caught.value


def admitted(cp=None, proposal=None, **kw):
    if cp is None:
        cp, proposal = f4_run()
    kw.setdefault("trust", make_trust())
    return do_import(cp, proposal, **kw)


# ============================================================================================================== positive control (N01) and markers
def test_N01_valid_evidence_is_admitted_through_the_real_enforcement_boundary_and_the_markers_are_exactly_the_conservative_set():
    """STUB verifier: proves Replay's admission path and marker contract, not authentication."""
    cp, proposal = f4_run()
    trust = make_trust()
    bundle = do_import(cp, proposal, trust=trust)
    meta = bundle.metadata
    assert len(trust.verifier.calls) == 1
    assert bundle.import_reports[0].adapter_profile == I.BOUNDED_CUR_REGISTRY_AUTHENTICATED_PROFILE
    # E-2: registry_authenticated stays False, registry_origin stays unverified; claim A only
    assert meta["registry_authenticated"] is False and meta["registry_origin"] == "registry_origin_unverified"
    assert meta["control_plane_decision_authenticated"] is False
    expected = {
        "control_plane_profile": "registry-authenticated-selection/0.1",
        "registry_selection_verification": "admitted_by_operator_supplied_verifier_replay_holds_no_crypto",
        "registry_selection_admitted_by_injected_verifier": True,
        "registry_authentication_claim": "A_selection_signature_per_injected_verifier",
        "registry_trust_snapshot_attestation": "operator_supplied_unattested",
        "registry_verified_as_of": "2026-11-02T12:00:00Z",
        "registry_verified_time_mode": "as_of_historical",
        "registry_verified_scope": "decision_time_only",
        "registry_claims_asserted_by_verifier_verdict": ["selection_signature_by_snapshot_key", "record_binding", "issuer_grant_scope_operation", "time_window_at_T", "snapshot_floors_if_supplied",
                                     "effective_policy_digest_matches_signed_bound_over_operator_host_ages"],
        "registry_not_verified": ["verifier_genuineness", "cp_decision_fields_not_covered_by_signature", "action_id_not_in_signed_statement", "selection_is_latest",
                                  "effect_time_validity", "snapshot_correctness_independence", "substitution_by_other_genuine_selection", "real_world_issuer_identity"],
        "registry_trust_snapshot_id": "snap-1", "registry_trust_snapshot_version": 7,
        "registry_floors_applied": {"min_trust_snapshot_version": True, "last_accepted_snapshot": True},
        "registry_declared_source_revisions": {"control_plane": CP_REV, "registry": REG_REV, "attestation": "operator_declared_unattested"},
        "claim_scope_note": "mechanism verified with synthetic keys; Registry-origin authority not established; claim B not made; decision-time only; "
                            "operator trust inputs independence unverified",
        "effective_configuration_verification": "internal_consistency_only_registry_source_revision_unverified",
    }
    for key, value in expected.items():
        assert meta[key] == value, key
    (entry,) = meta["registry_evidence"]
    assert set(entry) == {"decision_id", "family", "registry_contract", "issuer_id", "selection_id", "epoch", "selection_digest", "bound_record_digest",
                          "effective_policy_digest", "trust_snapshot_fingerprint", "epoch_floor_applied", "admission_binding_digest"}
    assert (entry["issuer_id"], entry["selection_id"], entry["epoch"], entry["trust_snapshot_fingerprint"], entry["epoch_floor_applied"]) == ("issuer-test-1", "sel-f4-001", 3, "fp-7", False)
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", entry["admission_binding_digest"])
    # the exact marker set (success only): nothing beyond the declared keys was added to the structural metadata
    structural = set(do_import(*S.load("governed_executed"), selector=S.OLD_SELECTOR).metadata)
    assert set(meta) - structural == RE.SUCCESS_MARKER_KEYS - {"control_plane_profile", "effective_configuration_verification"}
    assert RE.SUCCESS_MARKER_KEYS <= set(meta)
    # the carried decision is retained verbatim, evidence included; nothing was altered
    assert [r.data for r in bundle.records if r.record_type == "runtime_decision"] == cp["decisions"]


def test_the_wire_request_has_exactly_the_frozen_keys_and_the_operators_inputs_not_the_records():
    cp, proposal = f4_run(host={"status_max_age_seconds": 60, "approval_max_age_seconds": 60})
    trust = make_trust(expected_host_ages={"status_max_age_seconds": 60, "approval_max_age_seconds": 60})
    admitted(cp, proposal, trust=trust)
    (request,) = trust.verifier.calls
    assert set(request) == S.WIRE_REQUEST_KEYS
    assert request["contract"] == "registry-evidence-verification-request/0.1"
    assert request["family"] == "f4-control-plane-age-bounds" and request["registry_contract"] == "r08-v2"
    assert request["selection_text"] is cp["decisions"][0]["selection_evidence"]["selection_text"] or request["selection_text"] == SELECTION
    assert (request["selection_text"], request["record_text"]) == (SELECTION, RECORD)
    assert request["expected_context"] == CTX and request["expected_operation_id"] == OPERATION
    assert request["verification_time"] == T0 and request["verification_time_utc"] == "2026-11-02T12:00:00Z"
    assert request["min_trust_snapshot_version"] == 5 and request["last_accepted_snapshot"] == [7, "fp-7"]
    assert request["host_policy"] == HOST and set(request["host_policy"]) == {"status_max_age_seconds", "approval_max_age_seconds"}
    assert isinstance(request["trust_snapshot"], S.OpaqueSnapshot)


def test_the_stub_verdict_the_tests_use_has_exactly_the_frozen_verdict_keys():
    stub = LogicOnlyStubVerifier()
    trust = make_trust(verifier=stub)
    cp, proposal = f4_run()
    admitted(cp, proposal, trust=trust)
    verdict = stub.verify_selection_evidence(stub.calls[0])
    assert set(verdict) == S.WIRE_VERDICT_KEYS and set(verdict["layers"]) == set(LAYERS) == set(RE.LAYERS_V2)


def test_P_renewal_two_authorized_decisions_with_different_selections_both_verify_for_one_configuration():
    cp, proposal = f4_run()
    second = copy.deepcopy(cp["decisions"][0])
    second["decision_id"] = "dec-renewal-2"
    second["selection_evidence"] = evidence(ALT_SELECTION, ALT_RECORD)
    second["effect_id"] = None
    cp["decisions"].append(second)
    trust = make_trust()
    bundle = do_import(cp, None, trust=trust)
    assert len(trust.verifier.calls) == 2
    assert [e["selection_id"] for e in bundle.metadata["registry_evidence"]] == ["sel-f4-001", "sel-f4-002"]
    assert len({e["admission_binding_digest"] for e in bundle.metadata["registry_evidence"]}) == 2


def test_N19_replay_side_non_ascii_signed_content_passes_byte_for_byte_and_replay_never_serialises_the_carried_texts(monkeypatch):
    """Replay side of N19 only. The real ensure_ascii=True signing-bytes positive/negative needs PyNaCl and belongs to the Registry/Control Plane PRs. Here: the texts reach the
    verifier unchanged (same str), are hashed as UTF-8 only, and no json.dumps/canonical_bytes/json.loads ever sees a carried text."""
    seen = []

    def walk(x):
        if isinstance(x, str):
            seen.append(x)
        elif isinstance(x, Mapping):
            for k, v in x.items():
                walk(k), walk(v)
        elif isinstance(x, (list, tuple, set, frozenset)):
            for v in x:
                walk(v)
        elif isinstance(x, (bytes, bytearray)):
            seen.append(bytes(x).decode("utf-8", "replace"))

    real_dumps, real_loads, real_canonical = json.dumps, json.loads, RC.canonical_bytes

    def spy_dumps(obj, *a, **k):
        walk(obj)
        return real_dumps(obj, *a, **k)

    def spy_loads(s, *a, **k):
        walk(s)
        return real_loads(s, *a, **k)

    def spy_canonical(obj):
        walk(obj)
        return real_canonical(obj)
    cp, proposal = f4_run(SELECTION_NONASCII, RECORD_NONASCII)
    trust = make_trust()
    monkeypatch.setattr(json, "dumps", spy_dumps)
    monkeypatch.setattr(json, "loads", spy_loads)
    for module in (RC, I, EC, RE):
        if hasattr(module, "canonical_bytes"):
            monkeypatch.setattr(module, "canonical_bytes", spy_canonical)
    bundle = do_import(cp, proposal, trust=trust)
    assert any(a == "ténant-a" or "ténant-a" in a for a in [SELECTION_NONASCII]) and len(seen) > 0
    carried = {SELECTION_NONASCII, RECORD_NONASCII}
    assert not [s for s in seen if any(c in s for c in carried)], "a carried text reached json.dumps/json.loads/canonical_bytes"
    (request,) = trust.verifier.calls
    assert request["selection_text"] == SELECTION_NONASCII and request["record_text"] == RECORD_NONASCII
    assert bundle.metadata["registry_evidence"][0]["selection_id"] == "sel-f4-003"
    verdict = LogicOnlyStubVerifier().verify_selection_evidence(request)
    assert verdict["selection_text_sha256"] == S.sha(SELECTION_NONASCII)  # UTF-8 hash of the exact str


def test_the_registry_evidence_module_never_imports_json_or_the_registry_or_crypto():
    tree = ast.parse((SRC / "registry_evidence.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(("." * node.level) + (node.module or ""))
    assert imported <= {"__future__", "hashlib", "os", "re", "collections.abc", "dataclasses", "datetime", "typing", ".instants", ".reconstruction", ".importers",
                        ".refusal_evidence"}, imported
    calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not {c for c in calls if c.startswith("json.")} and "canonical_bytes" in calls  # canonical_bytes only on the hash/id binding body (see the spy test)


def test_no_source_module_imports_a_registry_package_or_a_crypto_library_and_the_dependency_list_is_unchanged():
    banned_prefixes = ("registry_", "nacl", "cryptography", "Crypto", "ed25519", "pynacl", "cffi")
    for path in SRC.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            assert not [n for n in names if n.split(".")[0].startswith(banned_prefixes)], (path.name, names)
    pyproject = (REPO / "pyproject.toml").read_text()
    match = re.search(r"^dependencies = \[(.*?)\]", pyproject, re.S | re.M)
    assert [d.strip().strip('",') for d in match.group(1).split("\n") if d.strip()] == ["pydantic>=2.0"]
    assert "optional-dependencies" in pyproject and "nacl" not in pyproject.lower()


# ============================================================================================================== verifier-relayed outcomes (N02-N04, N08, N12-N15)
@pytest.mark.parametrize("code,note", [
    ("signature_invalid", "N02 forged signature"), ("issuer_untrusted", "N03 unknown signer"), ("issuer_not_authorized", "N04 wrong issuer grant"),
    ("record_digest_mismatch", "N08 substituted record"), ("issuer_key_revoked", "N12 revoked key"), ("selection_withdrawn", "N13 withdrawn selection"),
    ("selection_epoch_stale", "N14 below-min epoch"), ("trust_snapshot_expired", "N15 expired snapshot at explicit time"),
    ("trust_snapshot_version_stale", "snapshot floor"), ("selection_not_yet_effective", "time"), ("selection_expired", "time"), ("selection_scope_mismatch", "signed scope")])
def test_verifier_refusals_are_relayed_as_typed_unverified_codes_with_no_fallback(code, note):
    """STUB relays a refusal code; proves Replay maps ok:False to registry_evidence_unverified:<code> and never falls back to structural-only or caller-trusted match."""
    cp, proposal = f4_run()
    trust = make_trust(verifier=LogicOnlyStubVerifier(refuse=code))
    refused(cp, proposal, "registry_evidence_unverified:" + code, trust=trust, calls=1)
    # the fallback WAS available: the very same record is accepted structurally under the old selector once the evidence member is removed
    stripped = copy.deepcopy(cp)
    del stripped["decisions"][0]["selection_evidence"]
    assert do_import(stripped, proposal, selector=S.OLD_SELECTOR).metadata["effective_configuration_verification"].startswith("internal_consistency_only")


def test_N02_N08_the_stub_refuses_an_altered_selection_or_record_text_and_replay_relays_it():
    cp, proposal = f4_run()
    forged = copy.deepcopy(cp)
    forged["decisions"][0]["selection_evidence"]["selection_text"] = SELECTION + " "
    refused(forged, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(), calls=1)
    swapped = copy.deepcopy(cp)
    swapped["decisions"][0]["selection_evidence"]["record_text"] = ALT_RECORD
    refused(swapped, proposal, "registry_evidence_unverified:record_digest_mismatch", trust=make_trust(), calls=1)


@pytest.mark.parametrize("bad_code", ["", "Signature_Invalid", "a" * 65, "sig-invalid", "sig invalid", VERIFIER_SECRET, "x;y", None, 7, "é"])
def test_a_refusal_verdict_with_an_unclean_code_is_malformed_and_never_echoed(bad_code):
    cp, proposal = f4_run()
    verdict = {"contract": "registry-evidence-verdict/0.1", "ok": False, "code": bad_code, "authenticated": False}
    refused(cp, proposal, "registry_evidence_verdict_malformed", trust=make_trust(verifier=LogicOnlyStubVerifier(replace=verdict)), calls=1)


# ============================================================================================================== selector / sentinel / mode matrix (N17, N18)
def test_N17_selector_without_trust_is_refused_it_never_runs_structural_only():
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_trust_missing")


@pytest.mark.parametrize("selector", [None, S.OLD_SELECTOR])
def test_N17_trust_without_the_authenticated_selector_is_refused_including_plain_and_old_governed(selector):
    cp, proposal = f4_run()
    trust = make_trust()
    refused(cp, proposal, "registry_evidence_unsupported_profile", trust=trust, selector=selector, calls=0)
    stripped = copy.deepcopy(cp)
    del stripped["decisions"][0]["selection_evidence"]
    refused(stripped, proposal, "registry_evidence_unsupported_profile", trust=trust, selector=selector, calls=0)


@pytest.mark.parametrize("value", [None, "", 0, False, b"", [], {}, (), "trust", {"ok": True, "authenticated": True}, True, 1, object(), set()])
def test_N16_N17_any_value_passed_for_the_trust_keyword_is_fail_closed_and_none_is_missing_not_unset(value):
    cp, proposal = f4_run()
    code = "registry_evidence_trust_missing" if value is None else "registry_evidence_trust_malformed"
    refused(cp, proposal, code, registry_evidence_trust=value)


def test_N17_presence_of_selection_evidence_alone_never_selects_the_profile_and_is_refused_elsewhere():
    cp, proposal = f4_run()
    refused(cp, proposal, "undeclared_member", selector=None)            # plain current profile
    refused(cp, proposal, "undeclared_member", selector=S.OLD_SELECTOR)  # old governed selector
    refused(cp, proposal, "undeclared_member", selector=None, revision=I.CONTROL_PLANE_REVISION)
    refused(cp, proposal, "undeclared_member", selector=S.OLD_SELECTOR, expected_effective_configuration_digest=cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]["digest"])


@pytest.mark.parametrize("selector", [SELECTOR + " ", " " + SELECTOR, SELECTOR.upper(), "registry-authenticated-selection", "registry-authenticated-selection/0.2", "registry-authenticated-*",
                                      "latest", "control-plane-current-stack-registry-authenticated-selection-0.1@operator-declared-revision", True, 1, b"x", [SELECTOR], {"p": SELECTOR}])
def test_the_selector_is_the_exact_string_only(selector):
    cp, proposal = f4_run()
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector"):
        do_import(cp, proposal, trust=make_trust(), selector=selector)


def test_a_str_subclass_selector_is_refused():
    class Sub(str):
        pass
    cp, proposal = f4_run()
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector"):
        do_import(cp, proposal, trust=make_trust(), selector=Sub(SELECTOR))


@pytest.mark.parametrize("revision", [I.CONTROL_PLANE_P2_REVISION, I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_F5B_REVISION, I.CONTROL_PLANE_SECURITY_REVISION,
                                      I.CONTROL_PLANE_REVISION, S.CUR_CP[:8], "latest", CP_REV])
def test_the_authenticated_selector_is_valid_only_with_the_current_generation_revision(revision):
    cp, proposal = f4_run()
    trust = make_trust()
    with pytest.raises(ImportContractError, match="unsupported Control Plane profile selector|unsupported Control Plane revision"):
        do_import(cp, proposal, trust=trust, revision=revision)
    assert trust.verifier.calls == []


@pytest.mark.parametrize("digest", [None, "", "sha256:" + "a" * 64, "x", 0, False, b""])
def test_N18_the_caller_trusted_digest_together_with_the_authenticated_selector_is_a_conflict_not_a_fallback(digest):
    cp, proposal = f4_run()
    trust = make_trust()
    real = cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]["digest"]
    for value in (digest, real):
        refused(cp, proposal, "registry_evidence_conflicting_modes", trust=trust, expected_effective_configuration_digest=value, calls=0)
    refused(cp, proposal, "registry_evidence_conflicting_modes", expected_effective_configuration_digest=real)  # even without trust


def test_N18_a_verifier_that_says_not_ok_never_falls_back_to_the_caller_trusted_digest_match():
    cp, proposal = f4_run()
    ec = cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]
    stripped = copy.deepcopy(cp)
    del stripped["decisions"][0]["selection_evidence"]
    # the caller-trusted match WOULD succeed for this exact configuration under the old selector ...
    trusted = do_import(stripped, proposal, selector=S.OLD_SELECTOR, expected_effective_configuration_digest=ec["digest"])
    assert trusted.metadata["effective_configuration_verification"] == "caller_trusted_configuration_match"
    # ... and is not reachable from the authenticated profile
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(verifier=LogicOnlyStubVerifier(refuse="signature_invalid")), calls=1)


# ============================================================================================================== N16 verdict injection
@dataclass
class VerdictShaped:
    ok: bool = True
    authenticated: bool = True
    code: object = None


class ShapedMapping(Mapping):
    def __init__(self, d):
        self._d = d

    def __getitem__(self, k):
        return self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)


class DictSub(dict):
    pass


def good_verdict(request):
    return LogicOnlyStubVerifier().verify_selection_evidence(request)


@pytest.mark.parametrize("make", [
    lambda v: ShapedMapping(v),                       # a Mapping that is not a dict
    lambda v: DictSub(v),                             # dict subclass
    lambda v: types.MappingProxyType(v),
    lambda v: "ok", lambda v: "true", lambda v: True, lambda v: 1, lambda v: None, lambda v: VerdictShaped(), lambda v: json.dumps(v), lambda v: [v], lambda v: (v,),
    lambda v: b"ok", lambda v: object(), lambda v: iter([v])])
def test_N16_a_verdict_that_is_not_a_plain_dict_grants_nothing(make):
    cp, proposal = f4_run()
    probe = good_verdict(S.make_trust().verifier.calls or _request_for(cp, proposal))
    trust = make_trust(verifier=LogicOnlyStubVerifier(replace=make(probe)))
    refused(cp, proposal, "registry_evidence_verdict_malformed", trust=trust, calls=1)


def _request_for(cp, proposal):
    trust = make_trust()
    do_import(cp, proposal, trust=trust)
    return trust.verifier.calls[0]


@pytest.mark.parametrize("mutate", [
    lambda v, r: v.update(ok="true"), lambda v, r: v.update(ok=1), lambda v, r: v.update(ok=None), lambda v, r: v.update(authenticated=1), lambda v, r: v.update(authenticated="yes"),
    lambda v, r: v.update(extra=True), lambda v, r: v.pop("effective_values"), lambda v, r: v.pop("layers"), lambda v, r: v.update(contract="registry-evidence-verdict/0.2"),
    lambda v, r: v.update(layers={**v["layers"], "extra": "pass"}), lambda v, r: v["layers"].pop("disposition"), lambda v, r: v["layers"].update(time="PASS"),
    lambda v, r: v["layers"].update(time=True), lambda v, r: v.update(epoch=True), lambda v, r: v.update(epoch=0), lambda v, r: v.update(trust_snapshot_version=True),
    lambda v, r: v.update(effective_values={"status_max_age_seconds": 60}), lambda v, r: v.update(effective_values={**v["effective_values"], "x": 1}),
    lambda v, r: v.update(effective_values={"status_max_age_seconds": True, "approval_max_age_seconds": 60}), lambda v, r: v.update(floors_applied={"min_trust_snapshot_version": True}),
    lambda v, r: v.update(floors_applied={"min_trust_snapshot_version": 1, "last_accepted_snapshot": True}), lambda v, r: v.update(epoch_floor_applied=0),
    lambda v, r: v.update(verifier_implementation="stub"), lambda v, r: v.update(verifier_implementation={"name": "x"}), lambda v, r: v.update(effective_policy_digest="sha256:abc"),
    lambda v, r: v.update(issuer_id=""), lambda v, r: v.update(selection_id=7), lambda v, r: v.update(bound_record_digest=None), lambda v, r: v.update(code=""),
    lambda v, r: v.update(code=VERIFIER_SECRET)])
def test_N16_N11_a_verdict_outside_the_closed_shape_is_malformed(mutate):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_verdict_malformed", trust=make_trust(verifier=LogicOnlyStubVerifier(mutate=mutate)), calls=1)


def test_N16_a_verdict_bearing_record_field_or_bundle_metadata_or_evidence_text_grants_nothing():
    """Verdict-shaped material in the record, in the evidence texts or claimed in metadata is plain data: only the injected verifier's return value is ever consulted."""
    fake = {"ok": True, "authenticated": True, "layers": {n: "pass" for n in LAYERS}, "registry_authenticated": True}
    cp, proposal = f4_run()
    cp["decisions"][0]["registry_verdict"] = fake
    cp["decisions"][0]["registry_selection_admitted_by_injected_verifier"] = True
    cp["registry_authenticated"] = True
    cp["metadata"] = {"registry_selection_admitted_by_injected_verifier": True, "control_plane_profile": SELECTOR}
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(verifier=LogicOnlyStubVerifier(refuse="signature_invalid")), calls=1)
    # a verdict inside the carried evidence object is an unknown member
    smuggled = copy.deepcopy(f4_run()[0])
    smuggled["decisions"][0]["selection_evidence"]["verdict"] = fake
    refused(smuggled, proposal, "selection_evidence_malformed", trust=make_trust(), calls=0)
    # a verdict-shaped JSON as the signed text reaches only the verifier, which decides
    text = json.dumps(fake)
    forged = copy.deepcopy(f4_run()[0])
    forged["decisions"][0]["selection_evidence"]["selection_text"] = text
    trust = make_trust()
    refused(forged, proposal, "registry_evidence_unverified:signature_invalid", trust=trust, calls=1)
    assert trust.verifier.calls[0]["selection_text"] == text


def test_N16_the_trust_object_cannot_carry_a_verdict_and_no_replay_api_takes_one():
    cp, proposal = f4_run()
    verdict_like = {"ok": True, "authenticated": True, "layers": {n: "pass" for n in LAYERS}}
    for bad in (verdict_like, types.SimpleNamespace(**verdict_like), VerdictShaped(), True, "admitted"):
        refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=bad)
    import inspect
    names = set(inspect.signature(I.import_bounded_workflow).parameters) | set(inspect.signature(reverify_retained_registry_evidence).parameters)
    assert not {n for n in names if "verdict" in n or "admitted" in n or "authenticated" in n}
    with pytest.raises(ImportContractError) as caught:
        make_trust(verifier=verdict_like)
    assert caught.value.code == "registry_evidence_trust_malformed"


def test_N16_a_verifier_that_is_a_bare_function_or_class_or_mapping_is_not_a_verifier():
    cp, proposal = f4_run()
    for bad in (lambda request: {"ok": True}, LogicOnlyStubVerifier, {"verify_selection_evidence": lambda r: {}}, "verify_selection_evidence", b"x", 1, None,
                types.SimpleNamespace(), types.SimpleNamespace(verify_selection_evidence=None), types.SimpleNamespace(verify_selection_evidence="x")):
        refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=raw_trust(verifier=bad))


# ============================================================================================================== N20 admission conjunction
def _verdict_mutating(fn):
    return make_trust(verifier=LogicOnlyStubVerifier(mutate=lambda v, r: fn(v)))


def test_N20_ok_true_with_authenticated_false_is_refused():
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_not_authenticated", trust=_verdict_mutating(lambda v: v.update(authenticated=False)), calls=1)


def test_N20_authenticated_true_with_ok_false_is_refused_as_unverified():
    cp, proposal = f4_run()
    verdict = {"contract": "registry-evidence-verdict/0.1", "ok": False, "code": "signature_invalid", "authenticated": True, "layers": {n: "pass" for n in LAYERS}}
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(verifier=LogicOnlyStubVerifier(replace=verdict)), calls=1)
    verdict["code"] = None  # ok False without any code
    refused(cp, proposal, "registry_evidence_verdict_malformed", trust=make_trust(verifier=LogicOnlyStubVerifier(replace=verdict)), calls=1)


@pytest.mark.parametrize("layer", LAYERS)
@pytest.mark.parametrize("value", ["refuse", "not_evaluated"])
def test_N20_every_one_of_the_eleven_layers_must_be_pass(layer, value):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_not_authenticated", trust=_verdict_mutating(lambda v: v["layers"].update({layer: value})), calls=1)


def test_N20_only_the_five_layers_of_the_earlier_draft_passing_is_not_enough():
    cp, proposal = f4_run()
    five = ("authority", "scope", "time", "record_binding", "epoch")
    refused(cp, proposal, "registry_evidence_not_authenticated",
            trust=_verdict_mutating(lambda v: v["layers"].update({n: ("pass" if n in five else "not_evaluated") for n in LAYERS})), calls=1)


def test_N20_the_record_less_trap_record_binding_not_evaluated_is_refused():
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_not_authenticated", trust=_verdict_mutating(lambda v: v["layers"].update(record_binding="not_evaluated")), calls=1)


def test_N20_ok_true_with_a_code_is_refused_and_a_layer_missing_is_malformed():
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_not_authenticated", trust=_verdict_mutating(lambda v: v.update(code="signature_invalid")), calls=1)
    refused(cp, proposal, "registry_evidence_verdict_malformed", trust=_verdict_mutating(lambda v: v["layers"].pop("revocation")), calls=1)


# ============================================================================================================== echo checks
ECHO_MUTATIONS = {
    "selection_sha": lambda v: v.update(selection_text_sha256=S.sha("other")),
    "record_sha": lambda v: v.update(record_text_sha256=S.sha("other")),
    "family": lambda v: v.update(family="f5-action-class-age-bounds"),
    "registry_contract": lambda v: v.update(registry_contract="r08-v3"),
    "time": lambda v: v.update(verification_time_utc="2026-11-02T12:00:01Z"),
    "snapshot_id": lambda v: v.update(trust_snapshot_id="snap-2"),
    "snapshot_version": lambda v: v.update(trust_snapshot_version=8),
    "min_floor_not_applied": lambda v: v["floors_applied"].update(min_trust_snapshot_version=False),
    "last_floor_not_applied": lambda v: v["floors_applied"].update(last_accepted_snapshot=False),
}


@pytest.mark.parametrize("name", sorted(ECHO_MUTATIONS))
def test_echo_mismatch_is_refused(name):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_input_echo_mismatch", trust=_verdict_mutating(ECHO_MUTATIONS[name]), calls=1)


def test_echo_floors_applied_last_true_when_the_operator_supplied_none_is_a_mismatch_and_none_is_recorded_as_not_applied():
    cp, proposal = f4_run()
    trust = make_trust(last_accepted_snapshot=None, verifier=LogicOnlyStubVerifier(mutate=lambda v, r: v["floors_applied"].update(last_accepted_snapshot=True)))
    refused(cp, proposal, "registry_evidence_input_echo_mismatch", trust=trust, calls=1)
    trust = make_trust(last_accepted_snapshot=None)
    bundle = do_import(cp, proposal, trust=trust)
    assert trust.verifier.calls[0]["last_accepted_snapshot"] is None
    assert bundle.metadata["registry_floors_applied"] == {"min_trust_snapshot_version": True, "last_accepted_snapshot": False}


def test_echo_text_hashes_are_plain_lowercase_hex_exact_equality_no_prefix_no_uppercase():
    cp, proposal = f4_run()
    admitted(cp, proposal, trust=_verdict_mutating(lambda v: v.update(selection_text_sha256=S.sha(SELECTION), record_text_sha256=S.sha(RECORD))))
    for bad in ("sha256:" + S.sha(SELECTION), S.sha(SELECTION).upper(), S.sha(SELECTION) + " "):
        refused(cp, proposal, "registry_evidence_input_echo_mismatch", trust=_verdict_mutating(lambda v, b=bad: v.update(selection_text_sha256=b)), calls=1)
    refused(cp, proposal, "registry_evidence_input_echo_mismatch", trust=_verdict_mutating(lambda v: v.update(record_text_sha256="sha256:" + S.sha(RECORD))), calls=1)


# ============================================================================================================== N09 and E-5: effective digest / values / operator host ages
def test_N09_altered_effective_policy_digest_in_the_family_row_is_refused_even_when_resealed():
    cp, proposal = f4_run()
    forged = reseal_members(cp, lambda m: m["families"][0].__setitem__("effective_policy_digest", "sha256:" + "3" * 64))
    refused(forged, proposal, "registry_evidence_effective_digest_mismatch", trust=make_trust(), calls=1)
    unsealed = copy.deepcopy(cp)
    unsealed["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]["members"]["families"][0]["effective_policy_digest"] = "sha256:" + "3" * 64
    refused(unsealed, proposal, "schema_violation", trust=make_trust(), calls=0)  # the existing structural digest check fires first


def test_N09_looser_f4_scalars_resealed_with_the_old_family_digest_are_refused_by_value():
    cp, proposal = f4_run()
    forged = reseal_members(cp, lambda m: m["f4_scalars"].update(status_max_age_seconds=100, approval_max_age_seconds=100))
    refused(forged, proposal, "registry_evidence_effective_values_mismatch", trust=make_trust(), calls=1)


def test_N09_looser_f4_scalars_with_a_consistently_resealed_family_digest_are_refused_by_digest():
    cp, proposal = f4_run()
    loose = {"status_max_age_seconds": 100, "approval_max_age_seconds": 100}

    def mutate(m):
        m["f4_scalars"] = dict(loose)
        m["families"][0]["effective_policy_digest"] = S.policy_digest(loose)
    refused(reseal_members(cp, mutate), proposal, "registry_evidence_effective_digest_mismatch", trust=make_trust(), calls=1)


def test_E5_NF1_a_tighter_resealed_edit_is_detected_because_the_operators_host_ages_are_required():
    """p0-C's NF-1 (a tighter resealed edit is indistinguishable from a stricter host) is closed by E-5 for the F4 scalars: the verifier composes min(operator host ages,
    signed bound), so a recorded value below that is a mismatch. It remains undetected ONLY if the operator's expected_host_ages were themselves taken from the record."""
    cp, proposal = f4_run()
    tight = {"status_max_age_seconds": 30, "approval_max_age_seconds": 30}

    def mutate(m):
        m["f4_scalars"] = dict(tight)
        m["families"][0]["effective_policy_digest"] = S.policy_digest(tight)
    forged = reseal_members(cp, mutate)
    refused(forged, proposal, "registry_evidence_effective_digest_mismatch", trust=make_trust(), calls=1)
    # the residual: an operator who derives expected_host_ages FROM THE RECORD admits the edit (independence of the operator's inputs is not verifiable by Replay)
    bundle = do_import(forged, proposal, trust=make_trust(expected_host_ages=dict(tight)))
    assert "cp_decision_fields_not_covered_by_signature" in bundle.metadata["registry_not_verified"]


@pytest.mark.parametrize("operator_ages", [{"status_max_age_seconds": 90, "approval_max_age_seconds": 90}, {"status_max_age_seconds": 30, "approval_max_age_seconds": 30},
                                           {"status_max_age_seconds": 60, "approval_max_age_seconds": 59}, {"status_max_age_seconds": 61, "approval_max_age_seconds": 60}])
def test_expected_host_ages_that_differ_from_the_recorded_effective_values_are_refused_and_the_verifier_gets_the_operators_ages(operator_ages):
    cp, proposal = f4_run()
    trust = make_trust(expected_host_ages=dict(operator_ages))
    refused(cp, proposal, "registry_evidence_effective_digest_mismatch", trust=trust, calls=1)
    assert trust.verifier.calls[0]["host_policy"] == operator_ages != cp["decisions"][0]["binding"]["runtime_authority"]["effective_configuration"]["members"]["f4_scalars"]


def test_the_verdict_effective_digest_check_is_not_circular_it_uses_the_operators_ages_not_the_records_values():
    cp, proposal = f4_run()
    seen = []

    def mutate(verdict, request):
        seen.append(request["host_policy"])
    admitted(cp, proposal, trust=make_trust(verifier=LogicOnlyStubVerifier(mutate=mutate), expected_host_ages=dict(HOST)))
    assert seen == [HOST]


# ============================================================================================================== N10 / N11 evidence presence and shape
def test_N10_an_authorized_decision_without_selection_evidence_is_refused():
    cp, proposal = f4_run(with_evidence=False)
    trust = make_trust()
    refused(cp, proposal, "selection_evidence_missing", trust=trust, calls=0)


def test_N10_stripped_evidence_under_the_authenticated_selector_is_missing_not_structural_only():
    cp, proposal = f4_run()
    del cp["decisions"][0]["selection_evidence"]
    refused(cp, proposal, "selection_evidence_missing", trust=make_trust(), calls=0)


def test_N10_the_second_of_two_authorized_decisions_without_evidence_is_refused_before_any_verifier_call():
    cp, proposal = f4_run()
    second = copy.deepcopy(cp["decisions"][0])
    second["decision_id"] = "dec-2"
    second["effect_id"] = None
    del second["selection_evidence"]
    cp["decisions"].append(second)
    refused(cp, None, "selection_evidence_missing", trust=make_trust(), calls=0)


BIG = "x" * 65537


@pytest.mark.parametrize("ev_edit", [
    pytest.param(lambda e: [e], id="list-of-one"), pytest.param(lambda e: [e, copy.deepcopy(e)], id="duplicate-family-list"), pytest.param(lambda e: "text", id="str"),
    pytest.param(lambda e: None, id="null"), pytest.param(lambda e: [], id="empty-list"), pytest.param(lambda e: 7, id="int"),
    pytest.param(lambda e: {**e, "extra": 1}, id="extra-key"), pytest.param(lambda e: {k: v for k, v in e.items() if k != "operation_id"}, id="missing-operation_id"),
    pytest.param(lambda e: {k: v for k, v in e.items() if k != "record_text"}, id="missing-record_text"),
    pytest.param(lambda e: {**e, "version": "selection-evidence/0.2"}, id="version"), pytest.param(lambda e: {**e, "version": 1}, id="version-int"),
    pytest.param(lambda e: {**e, "selection_text": 7}, id="text-int"), pytest.param(lambda e: {**e, "record_text": b"bytes"}, id="text-bytes"),
    pytest.param(lambda e: {**e, "selection_text": ""}, id="empty-selection"), pytest.param(lambda e: {**e, "record_text": ""}, id="empty-record"),
    pytest.param(lambda e: {**e, "selection_text": BIG}, id="oversize-ascii"), pytest.param(lambda e: {**e, "record_text": "é" * 40000}, id="oversize-utf8-bytes"),
    pytest.param(lambda e: {**e, "verified_at": "2026-11-02T11:59:00"}, id="naive-verified_at"), pytest.param(lambda e: {**e, "verified_at": "2026-11-02T11:59:00+01:00"}, id="non-utc"),
    pytest.param(lambda e: {**e, "verified_at": "yesterday"}, id="bad-verified_at"), pytest.param(lambda e: {**e, "verified_at": None}, id="null-verified_at"),
    pytest.param(lambda e: {**e, "operation_id": ""}, id="empty-operation"), pytest.param(lambda e: {**e, "operation_id": 5}, id="operation-int"),
    pytest.param(lambda e: {**e, 7: "x"}, id="non-str-key"), pytest.param(lambda e: {**e, "trust_snapshot": {"id": "x"}}, id="trust-smuggled"),
    pytest.param(lambda e: {**e, "authenticated": True}, id="authenticated-smuggled")])
def test_N11_malformed_evidence_is_refused_before_the_verifier_is_called(ev_edit, request):
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"] = ev_edit(cp["decisions"][0]["selection_evidence"])
    trust = make_trust()
    # bytes / non-str keys are foreign types: the M-1 exact-type snapshot refuses them first with the existing typed code schema_violation
    code = "schema_violation" if any(i in request.node.name for i in ("text-bytes", "non-str-key")) else "selection_evidence_malformed"
    refused(cp, proposal, code, trust=trust, calls=0)


@pytest.mark.parametrize("text", ["ok\ud800", "\udfff", "a\udc00b"])
def test_N11_a_lone_surrogate_text_is_a_typed_refusal_never_an_uncaught_exception(text):
    """Through the importer the pre-existing record bound check (``_check_record_bounds``) refuses ANY unpaired surrogate first, with its own typed code
    ``schema_violation``; the verifier is never reached. The admission layer's own unencodable branch (``selection_evidence_malformed``) is pinned directly."""
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"]["selection_text"] = text
    trust = make_trust()
    refused(cp, proposal, "schema_violation", trust=trust, calls=0)
    cp["decisions"][0]["selection_evidence"]["selection_text"] = SELECTION
    cp["decisions"][0]["selection_evidence"]["record_text"] = text
    with pytest.raises(ImportContractError) as caught:
        RE.admit(cp["decisions"], RE.validate_trust(make_trust()))
    assert caught.value.code == "selection_evidence_malformed" and trust.verifier.calls == []


def test_N11_a_str_subclass_text_is_malformed():
    class Text(str):
        pass
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"]["selection_text"] = Text(SELECTION)
    refused(cp, proposal, "schema_violation", trust=make_trust(), calls=0)  # the exact-type snapshot (M-1) refuses it first
    with pytest.raises(ImportContractError) as caught:  # and the admission layer's own shape gate refuses it too
        RE.admit(cp["decisions"], RE.validate_trust(make_trust()))
    assert caught.value.code == "selection_evidence_malformed"


def test_N11_the_size_limit_is_exactly_65536_utf8_bytes():
    cp, proposal = f4_run()
    at_limit = "y" * 65536
    cp["decisions"][0]["selection_evidence"]["selection_text"] = at_limit
    trust = make_trust()
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=trust, calls=1)  # shape accepted, the stub (not Replay) refuses the content
    assert len(trust.verifier.calls[0]["selection_text"]) == 65536
    multibyte = "é" * 32768  # 65536 bytes exactly
    cp["decisions"][0]["selection_evidence"]["selection_text"] = multibyte
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(), calls=None)
    cp["decisions"][0]["selection_evidence"]["selection_text"] = multibyte + "z"
    refused(cp, proposal, "selection_evidence_malformed", trust=make_trust(), calls=0)


# ============================================================================================================== N21 family set
@pytest.mark.parametrize("edit,code", [
    (lambda e: e.update(family="f5-action-class-age-bounds"), "registry_evidence_family_set_mismatch"),
    (lambda e: e.update(family="f4"), "registry_evidence_family_set_mismatch"),
    (lambda e: e.update(contract_version="r08-v3"), "registry_evidence_family_set_mismatch"),
    (lambda e: e.update(contract_version="r08-v8"), "registry_evidence_family_set_mismatch")])
def test_N21_wrong_family_or_contract_on_the_evidence_is_refused(edit, code):
    cp, proposal = f4_run()
    edit(cp["decisions"][0]["selection_evidence"])
    refused(cp, proposal, code, trust=make_trust(), calls=0)


def test_N21_a_record_without_an_f4_ages_family_row_is_refused_including_the_empty_families_list():
    cp, proposal = f4_run()
    for families in (lambda m: [r for r in m["families"] if r["slot"] != "f4_ages"], lambda m: []):
        forged = reseal_members(cp, lambda m, f=families: m.__setitem__("families", f(m)))
        refused(forged, proposal, "registry_evidence_family_set_mismatch", trust=make_trust(), calls=0)


@pytest.mark.parametrize("families", [frozenset({"f4", "f5_class_age"}), frozenset({"f5_class_age"}), frozenset({"f4", "x"})])
def test_N21_a_required_family_set_that_is_not_exactly_f4_is_a_family_set_mismatch(families):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_family_set_mismatch", registry_evidence_trust=raw_trust(required_families=families))
    with pytest.raises(ImportContractError) as caught:
        make_trust(required_families=families)
    assert caught.value.code == "registry_evidence_family_set_mismatch"


@pytest.mark.parametrize("families", [frozenset(), {"f4"}, ["f4"], ("f4",), "f4", None, frozenset({4}), frozenset({"f4", 7})])
def test_N21_a_required_family_set_of_the_wrong_type_or_empty_is_a_malformed_trust(families):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=raw_trust(required_families=families))


# ============================================================================================================== N05/N06/N07 scope at the Replay level
@pytest.mark.parametrize("field", ["consumer_id", "tenant", "institution", "authority_domain"])
def test_N05_N07_operator_context_that_differs_from_the_record_scope_is_refused_before_the_verifier(field):
    cp, proposal = f4_run()
    ctx = RegistryExpectedContext(**{**CTX, field: CTX[field] + "-other"})
    trust = make_trust(expected_context=ctx)
    refused(cp, proposal, "registry_evidence_scope_mismatch", trust=trust, calls=0)


def test_N06_a_different_expected_action_id_is_refused_before_the_verifier():
    cp, proposal = f4_run()
    trust = make_trust(expected_action_id=ACTION + "-other")
    refused(cp, proposal, "registry_evidence_scope_mismatch", trust=trust, calls=0)


def test_N06_a_different_operation_between_operator_and_carried_evidence_is_refused_before_the_verifier():
    cp, proposal = f4_run()
    trust = make_trust(expected_operation_id="other-op", expected_context=RegistryExpectedContext(**{**CTX, "operation": "other-op"}))
    refused(cp, proposal, "registry_evidence_scope_mismatch", trust=trust, calls=0)
    cp["decisions"][0]["selection_evidence"]["operation_id"] = "other-op"
    refused(cp, proposal, "registry_evidence_scope_mismatch", trust=make_trust(), calls=0)


def test_N06_the_operator_context_operation_must_equal_expected_operation_id_at_trust_validation():
    with pytest.raises(ImportContractError) as caught:
        make_trust(expected_operation_id="other-op")
    assert caught.value.code == "registry_evidence_trust_malformed"


@pytest.mark.parametrize("field,value", [("consumer_id", "consumer-evil"), ("institution_id", "urn:cognous:institution:other"), ("authority_domain", "payments")])
def test_N05_N07_resealed_edits_of_the_scope_fields_the_structural_profile_cannot_see_are_now_detected(field, value):
    cp, proposal = f4_run()
    forged = reseal_members(cp, lambda m: m["scope"].__setitem__(field, value))
    # structural-only (old selector, evidence stripped) accepts the resealed edit: the known non-detection of the structural profile
    stripped = copy.deepcopy(forged)
    del stripped["decisions"][0]["selection_evidence"]
    assert do_import(stripped, proposal, selector=S.OLD_SELECTOR)
    refused(forged, proposal, "registry_evidence_scope_mismatch", trust=make_trust(), calls=0)


def test_N05_a_resealed_tenant_or_action_edit_is_refused_by_the_existing_structural_checks_first():
    cp, proposal = f4_run()
    refused(reseal_members(cp, lambda m: m["scope"].__setitem__("tenant_id", "tenant-beta")), proposal, "schema_violation", trust=make_trust(), calls=0)
    refused(reseal_members(cp, lambda m: m["scope"].__setitem__("action_id", "urn:cognous:action:other")), proposal, "schema_violation", trust=make_trust(), calls=0)


# ============================================================================================================== N28 verifier unavailable / error
def test_N28_verifier_unavailable_is_blocked_not_admitted_and_distinct_from_unverified():
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_verifier_unavailable", trust=make_trust(verifier=LogicOnlyStubVerifier(refuse="verifier_unavailable")), calls=1)
    verdict = {"contract": "registry-evidence-verdict/0.1", "ok": False, "code": "verifier_unavailable", "authenticated": True, "layers": {n: "pass" for n in LAYERS}}
    refused(cp, proposal, "registry_evidence_verifier_unavailable", trust=make_trust(verifier=LogicOnlyStubVerifier(replace=verdict)), calls=1)


@pytest.mark.parametrize("exc", [RuntimeError(VERIFIER_SECRET), ValueError(VERIFIER_SECRET), KeyError("k"), ImportError(VERIFIER_SECRET), type("Ed25519Unavailable", (Exception,), {})(VERIFIER_SECRET),
                                 ImportContractError(VERIFIER_SECRET, code="registry_evidence_trust_missing")])
def test_N28_a_verifier_that_raises_is_a_typed_error_with_no_fallback_and_no_echo(exc):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_verifier_error", trust=make_trust(verifier=LogicOnlyStubVerifier(raises=exc)), calls=1)


# ============================================================================================================== time modes
def test_time_mode_now_accepts_within_300_seconds_and_refuses_beyond(monkeypatch):
    cp, proposal = f4_run()
    for skew, ok in ((0, True), (299, True), (-300, True), (301, False), (-301, False), (86400, False)):
        monkeypatch.setattr(RE, "_utc_now", lambda s=skew: T0 + timedelta(seconds=s))
        if ok:
            assert admitted(cp, proposal, trust=make_trust(time_mode="now")).metadata["registry_verified_time_mode"] == "now"
        else:
            refused(cp, proposal, "registry_evidence_time_inconsistent", registry_evidence_trust=raw_trust(time_mode="now"))
            with pytest.raises(ImportContractError) as caught:
                make_trust(time_mode="now")
            assert caught.value.code == "registry_evidence_time_inconsistent"


def test_time_mode_as_of_does_no_clock_check_and_the_marker_says_historical(monkeypatch):
    monkeypatch.setattr(RE, "_utc_now", lambda: T0 + timedelta(days=900))
    cp, proposal = f4_run()
    meta = admitted(cp, proposal, trust=make_trust(time_mode="as_of")).metadata
    assert meta["registry_verified_time_mode"] == "as_of_historical" and meta["registry_verified_as_of"] == "2026-11-02T12:00:00Z"


def test_the_carried_verified_at_is_informational_and_never_used_as_the_verification_time():
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"]["verified_at"] = "2030-01-01T00:00:00Z"
    trust = make_trust()
    bundle = do_import(cp, proposal, trust=trust)
    assert trust.verifier.calls[0]["verification_time_utc"] == "2026-11-02T12:00:00Z" and bundle.metadata["registry_verified_as_of"] == "2026-11-02T12:00:00Z"


def test_a_non_utc_offset_is_normalised_to_utc_and_sub_second_precision_is_dropped():
    cp, proposal = f4_run()
    plus2 = timezone(timedelta(hours=2))
    trust = make_trust(verification_time=datetime(2026, 11, 2, 14, 0, 0, 999999, tzinfo=plus2))
    meta = do_import(cp, proposal, trust=trust).metadata
    assert meta["registry_verified_as_of"] == "2026-11-02T12:00:00Z"
    request = trust.verifier.calls[0]
    assert request["verification_time"] == T0 and request["verification_time_utc"] == "2026-11-02T12:00:00Z"


# ============================================================================================================== trust object validation
NAIVE = datetime(2026, 11, 2, 12, 0, 0)


class TimeSub(datetime):
    pass


class StrSub(str):
    pass


class IntSub(int):
    pass


TRUST_BAD = {
    "verification_time": [NAIVE, "2026-11-02T12:00:00Z", 1.0, None, TimeSub(2026, 11, 2, 12, tzinfo=timezone.utc), T0.date()],
    "time_mode": ["Now", "asof", "", None, True, StrSub("now"), "historical"],
    "min_trust_snapshot_version": [0, -1, True, False, 1.0, "5", None, IntSub(5)],
    "expected_host_ages": [{"status_max_age_seconds": 60}, {"status_max_age_seconds": 60, "approval_max_age_seconds": 60, "x": 1}, {"status_max_age_seconds": True, "approval_max_age_seconds": 60},
                           {"status_max_age_seconds": 0, "approval_max_age_seconds": 60}, {"status_max_age_seconds": 60.0, "approval_max_age_seconds": 60},
                           {"status_max_age_seconds": 2147483648, "approval_max_age_seconds": 60}, {}, None, [], "60", types.MappingProxyType(HOST), {1: 60, 2: 60}],
    "last_accepted_snapshot": [(0, "fp"), (7,), (7, "fp", 1), [7, "fp"], (True, "fp"), (7, ""), (7, 8), "7:fp", (7, StrSub("fp"))],
    "expected_action_id": ["", None, 7, StrSub(ACTION), ACTION + " x", "a*b"],
    "expected_operation_id": ["", None, 7, StrSub(OPERATION)],
    "control_plane_source_revision": ["b" * 39, "B" * 40, "g" * 40, None, 7, StrSub("b" * 40), "b" * 41],
    "registry_source_revision": ["c" * 39, "C" * 40, "", None, StrSub("c" * 40)],
    "trust_snapshot_ref": [None, ("snap-1", 7), {"snapshot_id": "snap-1", "version": 7}, types.SimpleNamespace(snapshot_id="snap-1", version=7)],
    "expected_context": [None, CTX, types.SimpleNamespace(**CTX)],
    "trust_snapshot": [None],
}


@pytest.mark.parametrize("name,value", [(n, v) for n, vs in TRUST_BAD.items() for v in vs], ids=lambda x: x if isinstance(x, str) else None)
def test_trust_object_validation_at_import_and_at_construction(name, value):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=raw_trust(**{name: value}))
    with pytest.raises(ImportContractError) as caught:
        make_trust(**{name: value})
    assert caught.value.code == "registry_evidence_trust_malformed"


@pytest.mark.parametrize("ref", [dict(snapshot_id="", version=7), dict(snapshot_id="snap-1", version=0), dict(snapshot_id="snap-1", version=True), dict(snapshot_id=StrSub("s"), version=7),
                                 dict(snapshot_id=None, version=7), dict(snapshot_id="snap-1", version="7")])
def test_trust_snapshot_ref_validation(ref):
    cp, proposal = f4_run()
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=raw_trust(trust_snapshot_ref=RegistryTrustSnapshotRef(**ref)))


@pytest.mark.parametrize("field", ["consumer_id", "tenant", "institution", "authority_domain", "operation"])
@pytest.mark.parametrize("bad", ["", None, 7, "has space", "star*", "\u0000nul", "x" * 129, "\ud800"])
def test_expected_context_field_validation(field, bad):
    cp, proposal = f4_run()
    ctx = RegistryExpectedContext(**{**CTX, field: bad})
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=raw_trust(expected_context=ctx))


def test_expected_host_ages_is_required_no_default_exists():
    kw = dict(verifier=LogicOnlyStubVerifier(), trust_snapshot=S.OpaqueSnapshot(), trust_snapshot_ref=RegistryTrustSnapshotRef(snapshot_id="snap-1", version=7),
              expected_context=RegistryExpectedContext(**CTX), expected_action_id=ACTION, expected_operation_id=OPERATION, verification_time=T0, time_mode="as_of",
              min_trust_snapshot_version=5, control_plane_source_revision=CP_REV, registry_source_revision=REG_REV)
    with pytest.raises(TypeError):
        RegistryEvidenceTrust(**kw)  # no expected_host_ages
    with pytest.raises(TypeError):
        RegistryEvidenceTrust(**{**kw, "expected_host_ages": dict(HOST), "unknown": 1})
    with pytest.raises(TypeError):
        RegistryEvidenceTrust(*kw.values())  # keyword-only
    cp, proposal = f4_run()
    trust = make_trust()
    object.__delattr__(trust, "expected_host_ages")
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=trust)


def test_a_trust_object_built_without_validation_is_rejected_and_a_subclass_is_not_a_trust_object():
    cp, proposal = f4_run()
    blank = object.__new__(RegistryEvidenceTrust)
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=blank)

    class Sub(RegistryEvidenceTrust):
        pass
    with pytest.raises(ImportContractError) as caught:
        Sub(**{f: getattr(make_trust(), f) for f in RE._TRUST_FIELDS})
    assert caught.value.code == "registry_evidence_trust_malformed"
    sub = object.__new__(Sub)  # a subclass instance smuggled past construction
    for f in RE._TRUST_FIELDS:
        object.__setattr__(sub, f, getattr(make_trust(), f))
    refused(cp, proposal, "registry_evidence_trust_malformed", registry_evidence_trust=sub)


def test_mutating_the_trust_object_during_verification_does_not_change_the_run():
    cp, proposal = f4_run()
    trust = make_trust()

    def mutate(verdict, request):
        for name, value in (("expected_action_id", "evil"), ("time_mode", "now"), ("expected_host_ages", {"status_max_age_seconds": 1, "approval_max_age_seconds": 1})):
            object.__setattr__(trust, name, value)
    object.__setattr__(trust, "verifier", LogicOnlyStubVerifier(mutate=mutate))
    meta = do_import(cp, proposal, trust=trust).metadata
    assert meta["registry_verified_time_mode"] == "as_of_historical" and meta["registry_evidence"][0]["selection_id"] == "sel-f4-001"


def test_N08_trust_inputs_come_only_from_the_argument_never_from_the_bundle():
    """Selector-, snapshot- or context-looking values placed all over the record change nothing: the operator's trust is the only source."""
    cp, proposal = f4_run()
    cp["trust_snapshot"] = {"snapshot_id": "snap-evil", "version": 99}
    cp["expected_context"] = dict(CTX, tenant="tenant-evil")
    cp["decisions"][0]["trust_snapshot"] = {"snapshot_id": "snap-evil"}
    cp["decisions"][0]["selection_evidence"]["verified_at"] = "2020-01-01T00:00:00Z"
    trust = make_trust()
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=make_trust(verifier=LogicOnlyStubVerifier(refuse="signature_invalid")), calls=1)
    bundle = do_import(cp, proposal, trust=trust)
    request = trust.verifier.calls[0]
    assert request["expected_context"] == CTX and request["verification_time_utc"] == "2026-11-02T12:00:00Z"
    assert bundle.metadata["registry_trust_snapshot_id"] == "snap-1"


# ============================================================================================================== no free-text echo
def test_no_trust_snapshot_or_verifier_free_text_reaches_the_bundle_or_any_exception():
    cp, proposal = f4_run()
    leaky = LogicOnlyStubVerifier(mutate=lambda v, r: v["verifier_implementation"].update(name=VERIFIER_SECRET, registry_revision=VERIFIER_SECRET))
    bundle = do_import(cp, proposal, trust=make_trust(verifier=leaky))
    dumped = json.dumps(bundle.model_dump(mode="json"), default=str)
    assert SNAPSHOT_SECRET not in dumped and VERIFIER_SECRET not in dumped
    assert SNAPSHOT_SECRET not in repr(make_trust()) and "OpaqueSnapshot" not in repr(make_trust())
    for trust in (make_trust(verifier=LogicOnlyStubVerifier(refuse="signature_invalid")), make_trust(verifier=LogicOnlyStubVerifier(raises=RuntimeError(VERIFIER_SECRET))),
                  make_trust(verifier=LogicOnlyStubVerifier(replace={"ok": True, "detail": VERIFIER_SECRET}))):
        error = None
        try:
            do_import(cp, proposal, trust=trust)
        except ImportContractError as exc:
            error = exc
        assert error is not None and not any(s in str(error) + repr(error.args) + str(error.code) for s in (SNAPSHOT_SECRET, VERIFIER_SECRET))


# ============================================================================================================== no leakage of markers outside the success path
def test_the_success_only_markers_exist_in_no_other_mode_and_the_other_modes_are_unchanged():
    cp, proposal = S.load("governed_executed")
    plain = json.loads((Path(__file__).parent / "fixtures" / "current_generation" / "valid" / "control_plane_run.json").read_text())
    runs = [(plain, None, {"selector": None}), (cp, proposal, {"selector": S.OLD_SELECTOR}),
            (cp, proposal, {"selector": S.OLD_SELECTOR, "expected_effective_configuration_digest": "sha256:74e7cda7975979258803766c340a55d5fbdb1ea85abfc6a8ae8be0549dad95b7"})]
    for record, prop, kw in runs:
        meta = do_import(record, prop, **kw).metadata
        assert not (SUCCESS_ONLY & set(meta)), kw
        assert meta.get("registry_authenticated", False) is False
        assert meta.get("registry_origin", "registry_origin_unverified") == "registry_origin_unverified"


def test_registry_authenticated_is_never_true_and_registry_origin_is_never_anything_but_unverified_on_success():
    meta = admitted().metadata
    assert meta["registry_authenticated"] is False and meta["registry_origin"] == "registry_origin_unverified"
    assert not [k for k, v in meta.items() if k.endswith("_authenticated") and k != "registry_authenticated" and v is not False and k != "control_plane_decision_authenticated"]


# ============================================================================================================== N22 binding and retained bundles
def dumped_bundle(**kw):
    cp, proposal = f4_run(**kw)
    trust = make_trust()
    return cp, proposal, do_import(cp, proposal, trust=trust).model_dump(mode="json")


def edit_retained(dumped, fn):
    dumped = copy.deepcopy(dumped)
    decision = next(r for r in dumped["records"] if r["record_type"] == "runtime_decision")
    fn(decision["data"])
    return dumped


def ec_of(data):
    return data["binding"]["runtime_authority"]["effective_configuration"]


def reseal_retained(data, mutate):
    ec = ec_of(data)
    mutate(ec["members"])
    ec["digest"] = EC.digest_of(ec["version"], ec["members"])


def test_N22_the_untouched_retained_bundle_reverifies_and_reproduces_the_binding_digest_even_at_a_later_time_and_newer_snapshot():
    cp, proposal, dumped = dumped_bundle()
    stored = dumped["metadata"]["registry_evidence"][0]["admission_binding_digest"]
    again = reverify_retained_registry_evidence(dumped, registry_evidence_trust=make_trust(verification_time=T0 + timedelta(days=3)))
    assert again.metadata["registry_evidence"][0]["admission_binding_digest"] == stored
    assert again.metadata["registry_verified_as_of"] == "2026-11-05T12:00:00Z" and again.bundle_id != dumped["bundle_id"]
    # a ReconstructionBundle object works too
    again2 = reverify_retained_registry_evidence(do_import(cp, proposal, trust=make_trust()), registry_evidence_trust=make_trust())
    assert again2.metadata["registry_evidence"][0]["admission_binding_digest"] == stored


def _scalars(m, status, approval):
    m["f4_scalars"] = {"status_max_age_seconds": status, "approval_max_age_seconds": approval}


TAMPER = [
    # (id, edit of the retained decision data, expected code)
    ("f4_scalars-unsealed", lambda d: ec_of(d)["members"]["f4_scalars"].update(status_max_age_seconds=61), "schema_violation"),
    ("family-digest-unsealed", lambda d: ec_of(d)["members"]["families"][0].update(effective_policy_digest="sha256:" + "4" * 64), "schema_violation"),
    ("scope-tenant-unsealed", lambda d: ec_of(d)["members"]["scope"].update(tenant_id="tenant-beta"), "schema_violation"),
    ("scope-consumer-unsealed", lambda d: ec_of(d)["members"]["scope"].update(consumer_id="consumer-evil"), "schema_violation"),
    ("effective-configuration-digest", lambda d: ec_of(d).update(digest="sha256:" + "5" * 64), "schema_violation"),
    ("f4_scalars-resealed-looser", lambda d: reseal_retained(d, lambda m: _scalars(m, 100, 100)), "registry_evidence_effective_values_mismatch"),
    ("f4_scalars-resealed-tighter", lambda d: reseal_retained(d, lambda m: _scalars(m, 30, 30)), "registry_evidence_effective_values_mismatch"),
    ("family-digest-resealed", lambda d: reseal_retained(d, lambda m: m["families"][0].update(effective_policy_digest="sha256:" + "6" * 64)), "registry_evidence_effective_digest_mismatch"),
    ("scope-consumer-resealed", lambda d: reseal_retained(d, lambda m: m["scope"].update(consumer_id="consumer-evil")), "registry_evidence_scope_mismatch"),
    ("scope-institution-resealed", lambda d: reseal_retained(d, lambda m: m["scope"].update(institution_id="urn:cognous:institution:other")), "registry_evidence_scope_mismatch"),
    ("scope-domain-resealed", lambda d: reseal_retained(d, lambda m: m["scope"].update(authority_domain="payments")), "registry_evidence_scope_mismatch"),
    ("scope-action-resealed", lambda d: reseal_retained(d, lambda m: m["scope"].update(action_id="urn:cognous:action:other")), "schema_violation"),
    ("evidence-selection-text", lambda d: d["selection_evidence"].update(selection_text=SELECTION + "x"), "registry_evidence_unverified:signature_invalid"),
    ("evidence-record-text", lambda d: d["selection_evidence"].update(record_text=RECORD + "x"), "registry_evidence_unverified:record_digest_mismatch"),
    ("evidence-stripped", lambda d: d.pop("selection_evidence"), "selection_evidence_missing"),
    ("evidence-operation", lambda d: d["selection_evidence"].update(operation_id="other-op"), "registry_evidence_scope_mismatch"),
]


@pytest.mark.parametrize("name,edit,code", TAMPER, ids=[t[0] for t in TAMPER])
def test_N22_tamper_after_verification_is_refused_on_re_verification(name, edit, code):
    """Covers: scope/tenant/f4_scalars/family digest/effective_configuration digest/evidence texts, each causing a typed refusal when admission is re-run by the operator."""
    cp, proposal, dumped = dumped_bundle()
    tampered = edit_retained(dumped, edit)
    trust = make_trust()
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = reverify_retained_registry_evidence(tampered, registry_evidence_trust=trust)
    assert result is None and caught.value.code == code, caught.value.code


def test_N22_substitution_by_another_genuine_selection_with_consistent_edits_is_caught_only_by_the_binding_digest():
    """A genuinely signed ALTERNATIVE pair verifies on its own; it is detected after the fact only because the retained admission_binding_digest no longer matches."""
    cp, proposal, dumped = dumped_bundle()
    swapped = edit_retained(dumped, lambda d: d["selection_evidence"].update(selection_text=ALT_SELECTION, record_text=ALT_RECORD))
    # Replay alone (no stored digest) admits the genuine alternative: substitution by another genuine selection is a stated non-detection
    stripped_meta = copy.deepcopy(swapped)
    stripped_meta["metadata"].pop("registry_evidence")
    fresh = reverify_retained_registry_evidence(stripped_meta, registry_evidence_trust=make_trust())
    assert fresh.metadata["registry_evidence"][0]["selection_id"] == "sel-f4-002"
    # with the stored digest the swap is detected
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = reverify_retained_registry_evidence(swapped, registry_evidence_trust=make_trust())
    assert result is None and caught.value.code == "registry_evidence_binding_mismatch"


@pytest.mark.parametrize("stored", [lambda e: e[0].update(admission_binding_digest="sha256:" + "7" * 64), lambda e: e.clear(), lambda e: e.append(dict(e[0])),
                                    lambda e: e[0].update(decision_id="other"), lambda e: e.__setitem__(0, "x")])
def test_N22_a_stored_binding_digest_that_differs_or_a_different_decision_set_is_a_binding_mismatch(stored):
    cp, proposal, dumped = dumped_bundle()
    changed = copy.deepcopy(dumped)
    stored(changed["metadata"]["registry_evidence"])
    refused_with = None
    with pytest.raises(ImportContractError) as caught:
        refused_with = reverify_retained_registry_evidence(changed, registry_evidence_trust=make_trust())
    assert refused_with is None and caught.value.code == "registry_evidence_binding_mismatch"
    for bad in ("x", {"a": 1}, 7):
        changed = copy.deepcopy(dumped)
        changed["metadata"]["registry_evidence"] = bad
        with pytest.raises(ImportContractError) as caught:
            reverify_retained_registry_evidence(changed, registry_evidence_trust=make_trust())
        assert caught.value.code == "registry_evidence_binding_mismatch"


MEMBER_EDITS = [
    ("other_scalars", lambda d: reseal_retained(d, lambda m: m["other_scalars"].update(clock_tolerance_seconds=6))),
    ("host_profile_digest", lambda d: reseal_retained(d, lambda m: m.update(host_profile_digest="sha256:" + "8" * 64))),
    ("other-family-row", lambda d: reseal_retained(d, lambda m: m["families"][1].update(effective_policy_digest="sha256:" + "9" * 64))),
    ("observation_policy", lambda d: reseal_retained(d, lambda m: m["observation_policy"].update(max_age_seconds=61))),
]


@pytest.mark.parametrize("name,edit", MEMBER_EDITS, ids=[n for n, _ in MEMBER_EDITS])
def test_N22_resealed_non_F4_member_edits_are_not_covered_by_the_signature_and_only_a_retained_binding_digest_notices_them(name, edit):
    """STATED NON-DETECTION (non-F4 members): the verifier checks only the F4 values, so a resealed edit of any other effective-configuration member passes admission. The
    stored admission_binding_digest covers effective_configuration.digest and so differs - but it is unsigned metadata an attacker who rewrites the bundle can also rewrite,
    so it is a consistency aid, never an authenticator."""
    cp, proposal, dumped = dumped_bundle()
    stored = dumped["metadata"]["registry_evidence"][0]["admission_binding_digest"]
    tampered = edit_retained(dumped, edit)
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = reverify_retained_registry_evidence(tampered, registry_evidence_trust=make_trust())
    assert result is None and caught.value.code == "registry_evidence_binding_mismatch"
    tampered["metadata"].pop("registry_evidence")  # the attacker also removes (or rewrites) the unsigned stored digest
    fresh = reverify_retained_registry_evidence(tampered, registry_evidence_trust=make_trust())
    assert fresh.metadata["registry_evidence"][0]["admission_binding_digest"] != stored  # recomputed over the edited configuration, admitted all the same
    assert "cp_decision_fields_not_covered_by_signature" in fresh.metadata["registry_not_verified"]
    assert fresh.metadata["control_plane_decision_authenticated"] is False and fresh.metadata["registry_authenticated"] is False


@pytest.mark.parametrize("name,edit", [("decision-reasons", lambda d: d.update(reasons=[])),
                                       ("decision-operation_horizon", lambda d: d.update(operation_horizon=None)),
                                       ("decision-time_source", lambda d: d.update(time_source="other"))])
def test_N22_decision_fields_are_claim_B_an_edit_passes_admission_and_the_binding_digest_does_not_move(name, edit):
    """STATED NON-DETECTION (claim B): result, reasons, times, time_source and operation_horizon are unsigned and unbound; Replay never claims them."""
    cp, proposal, dumped = dumped_bundle()
    stored = dumped["metadata"]["registry_evidence"][0]["admission_binding_digest"]
    fresh = reverify_retained_registry_evidence(edit_retained(dumped, edit), registry_evidence_trust=make_trust())
    assert fresh.metadata["registry_evidence"][0]["admission_binding_digest"] == stored
    assert "cp_decision_fields_not_covered_by_signature" in fresh.metadata["registry_not_verified"] and fresh.metadata["control_plane_decision_authenticated"] is False


@pytest.mark.parametrize("name,edit,code", [("evaluated_at", lambda d: d.update(evaluated_at="2026-01-01T00:00:00Z"), "evaluation_alias_mismatch"),
                                            ("recorded_at", lambda d: d.update(recorded_at="2026-01-01T00:00:00Z"), "recorded_before_evaluated")])
def test_N22_some_decision_time_edits_are_refused_by_the_pre_existing_structural_profile_not_by_the_new_one(name, edit, code):
    cp, proposal, dumped = dumped_bundle()
    with pytest.raises(ImportContractError) as caught:
        reverify_retained_registry_evidence(edit_retained(dumped, edit), registry_evidence_trust=make_trust())
    assert caught.value.code == code


def test_N22_the_binding_digest_covers_scope_scalars_family_row_texts_and_signed_members_but_not_time_or_snapshot():
    base = admitted(*f4_run()).metadata["registry_evidence"][0]["admission_binding_digest"]
    # time and snapshot reference/floors are excluded on purpose (honest later re-verification reproduces the digest)
    later = admitted(*f4_run(), trust=make_trust(verification_time=T0 + timedelta(days=1), min_trust_snapshot_version=6)).metadata["registry_evidence"][0]["admission_binding_digest"]
    assert later == base
    # a different genuine pair, or another operator context element, changes it
    other_pair = admitted(*f4_run(ALT_SELECTION, ALT_RECORD)).metadata["registry_evidence"][0]["admission_binding_digest"]
    assert other_pair != base


def test_retained_bundle_metadata_claiming_admission_is_ignored_by_reverification():
    cp, proposal = f4_run()
    stripped = copy.deepcopy(cp)
    del stripped["decisions"][0]["selection_evidence"]
    structural = do_import(stripped, proposal, selector=S.OLD_SELECTOR).model_dump(mode="json")
    structural["metadata"].update({"registry_selection_admitted_by_injected_verifier": True, "registry_authenticated": True, "control_plane_profile": SELECTOR,
                                   "registry_selection_verification": "admitted_by_operator_supplied_verifier_replay_holds_no_crypto",
                                   "registry_evidence": [{"decision_id": "x", "admission_binding_digest": "sha256:" + "a" * 64}]})
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = reverify_retained_registry_evidence(structural, registry_evidence_trust=make_trust())
    assert result is None and caught.value.code == "selection_evidence_missing"


def test_reverification_ignores_the_selector_recorded_in_metadata_and_needs_the_operators_trust():
    cp, proposal, dumped = dumped_bundle()
    dumped["metadata"]["control_plane_profile"] = S.OLD_SELECTOR
    dumped["metadata"]["control_plane_revision"] = I.CONTROL_PLANE_P2_REVISION
    fresh = reverify_retained_registry_evidence(dumped, registry_evidence_trust=make_trust())
    assert fresh.metadata["control_plane_profile"] == SELECTOR and fresh.metadata["control_plane_revision"] == S.CUR_CP
    with pytest.raises(TypeError):
        reverify_retained_registry_evidence(dumped)  # keyword-only and required
    with pytest.raises(ImportContractError) as caught:
        reverify_retained_registry_evidence(dumped, registry_evidence_trust=None)
    assert caught.value.code == "registry_evidence_trust_missing"
    with pytest.raises(ImportContractError) as caught:
        reverify_retained_registry_evidence(dumped, registry_evidence_trust={"ok": True})
    assert caught.value.code == "registry_evidence_trust_malformed"
    with pytest.raises(ImportContractError):
        reverify_retained_registry_evidence("not a bundle", registry_evidence_trust=make_trust())


def test_retained_authenticated_record_with_the_old_selector_is_undeclared_member_and_stripped_evidence_gives_structural_marker_only():
    cp, proposal, dumped = dumped_bundle()
    by = lambda kind: [r["data"] for r in sorted(dumped["records"], key=lambda r: r["source_sequence"]) if r["record_type"] == kind]
    from agent_replay_bundle.refusal_evidence import extend_retained_inputs
    rebuilt = extend_retained_inputs({"run_id": dumped["run_id"], "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
                                      "observations": by("effect_observation"), "reconciliations": by("reconciliation")}, dumped)
    refused(rebuilt, by("runtime_proposal")[0], "undeclared_member", selector=S.OLD_SELECTOR)
    refused(rebuilt, by("runtime_proposal")[0], "undeclared_member", selector=None)
    del rebuilt["decisions"][0]["selection_evidence"]
    meta = do_import(rebuilt, by("runtime_proposal")[0], selector=S.OLD_SELECTOR).metadata
    assert meta["effective_configuration_verification"] == "internal_consistency_only_registry_source_revision_unverified"
    assert not [k for k in meta if k.startswith("registry_")] and "claim_scope_note" not in meta


# ============================================================================================================== N23/N24: legacy outputs byte-identical; named-key guard
def test_N23_N24_every_existing_fixture_in_every_pre_existing_mode_and_revision_is_byte_identical_to_the_unmodified_base():
    from . import golden_legacy_outputs as G
    expected = json.loads(G.GOLDEN.read_text())
    actual = G.compute()
    assert set(actual) == set(expected) and len(expected) > 1000 and sum(v.startswith("ok:") for v in expected.values()) > 200
    assert [k for k in expected if actual[k] != expected[k]] == []


def _legacy_ok_combos():
    from . import golden_legacy_outputs as G
    expected = json.loads(G.GOLDEN.read_text())
    revisions = {r[:8]: r for r in {I.CONTROL_PLANE_REVISION, *I.CONTROL_PLANE_SUPPORTED_V2_REVISIONS}}
    for key, value in expected.items():
        name, rev, export, mode = key.split("|")
        if value.startswith("ok:") and mode in ("plain", "governed"):
            yield pytest.param(name, revisions[rev], export, mode, id=key)


@pytest.mark.parametrize("name,revision,export,mode", list(_legacy_ok_combos()))
def test_E3_named_key_guard_selection_evidence_is_refused_under_every_pre_existing_profile_and_revision(name, revision, export, mode):
    from . import golden_legacy_outputs as G
    folder = G.FIXTURES / name
    cp = json.loads((folder / "control_plane_run.json").read_text())
    proposal = json.loads((folder / "proposal.json").read_text()) if (folder / "proposal.json").exists() else None
    moltbot = json.loads((folder / export).read_text()) if export != "none" else None
    kw = {"control_plane_profile": S.OLD_SELECTOR} if mode == "governed" else {}
    I.import_bounded_workflow(copy.deepcopy(cp), proposal=copy.deepcopy(proposal), moltbot_export=copy.deepcopy(moltbot), control_plane_revision=revision, **kw)  # positive control
    cp["decisions"][0]["selection_evidence"] = evidence()
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = I.import_bounded_workflow(cp, proposal=proposal, moltbot_export=moltbot, control_plane_revision=revision, **kw)
    assert result is None and caught.value.code == "undeclared_member"


def test_E3_the_guard_is_by_name_only_and_does_not_close_the_decision_member_set():
    cp, proposal = S.load("governed_executed")
    cp["decisions"][0]["some_future_member"] = {"x": 1}  # unchanged historical behaviour: silently retained
    bundle = do_import(cp, proposal, selector=S.OLD_SELECTOR)
    assert [r.data for r in bundle.records if r.record_type == "runtime_decision"] == cp["decisions"]


def test_E3_selection_evidence_on_a_non_authorized_decision_is_refused_under_the_authenticated_profile_too():
    cp, proposal = f4_run()
    second = copy.deepcopy(cp["decisions"][0])
    second.update(decision_id="dec-hold", result="hold", effect_id=None)
    del second["binding"]["runtime_authority"]["effective_configuration"]
    del second["selection_evidence"]
    cp["decisions"].append(second)
    admitted(cp, None)  # positive control: a non-authorized decision WITHOUT the member is fine
    second["selection_evidence"] = evidence()
    trust = make_trust()
    refused(cp, None, "undeclared_member", trust=trust, calls=0)
    with pytest.raises(ImportContractError) as caught:
        RE.admit([second], RE.validate_trust(make_trust()))
    assert caught.value.code == "undeclared_member"


# ============================================================================================================== NF-2 and the deliberately weak spot
def test_NF2_a_stub_verifier_returning_a_self_consistent_pass_is_accepted_injected_verifier_genuineness_is_not_attested():
    """KNOWN NON-DETECTION (analogue of N03 for the verifier itself). Replay holds no crypto: a verifier that checks nothing but echoes consistently is indistinguishable
    from a genuine adapter. Text signed by nobody is admitted here. The markers say 'admitted_by_operator_supplied_verifier' and list verifier_genuineness as NOT verified."""
    nothing_signed = '{"nobody":"signed this"}'
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"].update(selection_text=nothing_signed, record_text=nothing_signed)
    liar = LogicOnlyStubVerifier(genuine={nothing_signed: (nothing_signed, {"status_max_age_seconds": 120, "approval_max_age_seconds": 120}, "issuer-nobody", "sel-fake-001", 9)})
    meta = do_import(cp, proposal, trust=make_trust(verifier=liar)).metadata
    assert meta["registry_selection_admitted_by_injected_verifier"] is True and meta["registry_authenticated"] is False
    assert "verifier_genuineness" in meta["registry_not_verified"] and meta["registry_trust_snapshot_attestation"] == "operator_supplied_unattested"


def test_N25_a_Control_Plane_decision_without_evidence_is_compatible_under_every_pre_existing_profile():
    cp, proposal = f4_run(with_evidence=False)
    assert do_import(cp, proposal, selector=S.OLD_SELECTOR).metadata["effective_configuration_verification"].startswith("internal_consistency_only")
    plain_cp, plain_proposal = S.load("governed_executed")
    assert "selection_evidence" not in plain_cp["decisions"][0] and do_import(plain_cp, plain_proposal, selector=S.OLD_SELECTOR)


def test_N27_cp_fields_not_covered_by_the_signature_are_never_labelled_authenticated():
    meta = admitted().metadata
    assert meta["control_plane_decision_authenticated"] is False and meta["registry_authenticated"] is False
    assert "cp_decision_fields_not_covered_by_signature" in meta["registry_not_verified"] and "action_id_not_in_signed_statement" in meta["registry_not_verified"]
    assert meta["registry_verified_scope"] == "decision_time_only" and "effect_time_validity" in meta["registry_not_verified"]


def test_the_verifier_is_called_once_per_authorized_decision_and_never_when_a_cheaper_check_refuses():
    cp, proposal = f4_run()
    trust = make_trust()
    do_import(cp, proposal, trust=trust)
    assert len(trust.verifier.calls) == 1
    bad = copy.deepcopy(cp)
    bad["decisions"][0]["binding"]["runtime_authority"]["catalogue_digest"] = "sha256:" + "b" * 64
    trust2 = make_trust()
    refused(bad, proposal, "schema_violation", trust=trust2, calls=0)  # existing structural check runs first


def test_the_authenticated_profile_id_does_not_relabel_the_record_with_the_b19c47dd_label():
    assert "b19c47dd" not in RE.BOUNDED_CUR_REGISTRY_AUTHENTICATED_PROFILE and I.BOUNDED_CUR_REGISTRY_AUTHENTICATED_PROFILE not in I.SECURITY_RUNTIME_BOUNDED_PROFILES
    assert RE.REGISTRY_AUTHENTICATED_SELECTION_PROFILE == "registry-authenticated-selection/0.1"
    meta = admitted().metadata
    assert meta["registry_declared_source_revisions"]["attestation"] == "operator_declared_unattested"


def test_cross_check_the_control_plane_golden_carried_evidence_shape_is_accepted_by_the_replay_shape_gate_and_reaches_the_verifier_unchanged():
    """Copy of the Control Plane worker's golden fixture (tests/fixtures/f4_selection_evidence_wire_0_1.json in cognous-control-plane). Shape/transport only: the stub does
    not verify its signature (no crypto in Replay)."""
    golden = json.loads((Path(__file__).parent / "fixtures" / "rw01_f4_poc_golden" / "f4_selection_evidence_wire_0_1.json").read_text())
    assert set(golden) == set(RE.EVIDENCE_KEYS)
    cp, proposal = f4_run()
    cp["decisions"][0]["selection_evidence"] = golden
    trust = make_trust(expected_operation_id=golden["operation_id"], expected_context=RegistryExpectedContext(**{**CTX, "operation": golden["operation_id"]}))
    refused(cp, proposal, "registry_evidence_unverified:signature_invalid", trust=trust, calls=1)  # the stub knows no signer; shape passed
    assert trust.verifier.calls[0]["selection_text"] == golden["selection_text"] and trust.verifier.calls[0]["record_text"] == golden["record_text"]


# ============================================================================================================== review conditions M-1 / L-1 (independent review of PR #84)
class ShiftyDecision(dict):
    """The reviewer's probe: the first read of ``selection_evidence`` returns the genuine signed pair, while the stored content (what iteration/``items`` yield) is forged."""
    def __init__(self, stored, genuine):
        super().__init__(stored)
        self._genuine, self._reads = genuine, 0

    def __getitem__(self, key):
        if key == "selection_evidence":
            self._reads += 1
            return self._genuine if self._reads == 1 else dict.__getitem__(self, key)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        return self[key] if key in self else default


@pytest.mark.parametrize("variant", ["getitem-get", "items-only"])
def test_M1_a_dict_subclass_decision_whose_reads_vary_is_refused_and_nothing_forged_is_persisted(variant):
    cp, proposal = f4_run()
    genuine = copy.deepcopy(cp["decisions"][0]["selection_evidence"])
    forged_decision = copy.deepcopy(cp["decisions"][0])
    forged_decision["selection_evidence"]["selection_text"] = '{"forged":"selection"}'
    forged_decision["selection_evidence"]["record_text"] = '{"forged":"record"}'
    cp["decisions"][0] = ShiftyDecision(forged_decision, genuine)
    trust = make_trust()
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = do_import_raw(cp, proposal, trust)
    assert result is None and caught.value.code == "schema_violation"
    assert trust.verifier.calls == []  # refused before any verification


def do_import_raw(cp, proposal, trust):
    """Like do_import but WITHOUT the deepcopy (a deepcopy would normalise the subclass away)."""
    return I.import_bounded_workflow(cp, proposal=proposal, control_plane_revision=S.CUR_CP, control_plane_profile=SELECTOR, registry_evidence_trust=trust)


@pytest.mark.parametrize("where", ["decision", "evidence", "text", "list", "binding"])
def test_M1_every_subclass_in_the_record_is_refused_under_the_authenticated_profile(where):
    class D(dict):
        pass

    class L(list):
        pass

    class T(str):
        pass
    cp, proposal = f4_run()
    d = cp["decisions"][0]
    if where == "decision":
        cp["decisions"][0] = D(d)
    elif where == "evidence":
        d["selection_evidence"] = D(d["selection_evidence"])
    elif where == "text":
        d["selection_evidence"]["selection_text"] = T(SELECTION)
    elif where == "list":
        cp["decisions"] = L(cp["decisions"])
    else:
        d["binding"] = D(d["binding"])
    trust = make_trust()
    result = None
    with pytest.raises(ImportContractError) as caught:
        result = do_import_raw(cp, proposal, trust)
    assert result is None and caught.value.code in ("schema_violation", "selection_evidence_malformed")
    assert trust.verifier.calls == []


def test_M1_the_persisted_decision_is_the_exact_snapshot_that_was_verified_even_if_the_caller_mutates_the_input_during_verification():
    cp, proposal = f4_run()
    target = cp["decisions"][0]["selection_evidence"]

    def mutate(verdict, request):
        target["selection_text"] = '{"forged":"after-verification"}'
        target["record_text"] = '{"forged":"after-verification"}'
    trust = make_trust(verifier=LogicOnlyStubVerifier(mutate=mutate))
    bundle = I.import_bounded_workflow(cp, proposal=proposal, control_plane_revision=S.CUR_CP, control_plane_profile=SELECTOR, registry_evidence_trust=trust)
    persisted = next(r.data for r in bundle.records if r.record_type == "runtime_decision")["selection_evidence"]
    assert (persisted["selection_text"], persisted["record_text"]) == (SELECTION, RECORD) == (trust.verifier.calls[0]["selection_text"], trust.verifier.calls[0]["record_text"])
    assert bundle.metadata["registry_evidence"][0]["selection_id"] == "sel-f4-001"


def test_M1_plain_exact_typed_input_is_unchanged_by_the_snapshot_and_other_modes_never_snapshot():
    cp, proposal = f4_run()
    bundle = do_import(cp, proposal, trust=make_trust())
    assert [r.data for r in bundle.records if r.record_type == "runtime_decision"] == cp["decisions"]
    class D(dict):
        pass
    legacy_cp, legacy_proposal = S.load("governed_executed")
    legacy_cp["decisions"][0] = D(legacy_cp["decisions"][0])
    assert I.import_bounded_workflow(legacy_cp, proposal=legacy_proposal, control_plane_revision=S.CUR_CP, control_plane_profile=S.OLD_SELECTOR)  # legacy behaviour untouched


def test_L1_a_verifier_that_rewrites_its_request_cannot_change_what_replay_compares_against():
    """Defence in depth against a lying verifier (NF-2 still applies): echo expectations are fixed before the call and the verifier receives its own copy."""
    cp, proposal = f4_run()

    def rewrite(verdict, request):
        request["selection_text"], request["record_text"] = S.ALT_SELECTION, S.ALT_RECORD
        request["family"], request["verification_time_utc"] = "other", "2000-01-01T00:00:00Z"
        request["host_policy"]["status_max_age_seconds"] = 1
        request["expected_context"]["tenant"] = "evil"
        # a self-consistent verdict for the ALTERNATIVE pair
        verdict.update(selection_text_sha256=S.sha(S.ALT_SELECTION), record_text_sha256=S.sha(S.ALT_RECORD), family="other", verification_time_utc="2000-01-01T00:00:00Z")
    trust = make_trust(verifier=LogicOnlyStubVerifier(mutate=rewrite))
    refused(cp, proposal, "registry_evidence_input_echo_mismatch", trust=trust, calls=1)
    # and the operator's trust object / a second run are unaffected by what the stub did to its request copy
    assert admitted(cp, proposal).metadata["registry_evidence"][0]["selection_id"] == "sel-f4-001"


def test_L3_the_verifier_protocol_docstring_names_the_real_adapter_path():
    doc = RE.RegistryEvidenceVerifier.__doc__
    assert "registry_consumer/evidence_verifier.py::RegistryEvidenceVerifierV2" in doc and "registry_successor.v2_verified_selection" not in doc


def test_L4_the_verifier_asserted_claims_marker_is_renamed_and_the_old_name_is_gone():
    meta = admitted().metadata
    assert "registry_claims_asserted_by_verifier_verdict" in meta and "registry_verified_claims" not in meta
    assert "registry_verified_claims" not in RE.SUCCESS_MARKER_KEYS
