"""Registry-authenticated selection profile (``registry-authenticated-selection/0.1``), RW-01-F4-PoC.

WHAT THIS MODULE IS. The Replay-side ENFORCEMENT BOUNDARY for original signed Registry selection evidence that the Control Plane carried in an authorized
decision's top-level ``selection_evidence`` member (single object, ``selection-evidence/0.1``). It selects an explicit, fail-closed profile, validates an
operator-supplied trust object, hands the ORIGINAL ``selection_text``/``record_text`` strings to an operator-supplied verifier, gates the verdict through a closed
conjunction and binds the admission to the exact Replay record.

WHAT THIS MODULE IS NOT.
* It holds NO cryptography, imports NOTHING from the Registry and adds NO dependency. Whether a signature was really checked is decided entirely by the
  injected verifier, which Replay cannot inspect or attest (known non-detection NF-2: a lying or stub verifier that returns a self-consistent verdict is accepted).
* It never parses or re-serialises the carried texts (no ``canonical_bytes`` / ``json.dumps`` on them); it only hashes ``text.encode("utf-8")`` for the echo check.
* It never establishes claim B (that the Control Plane decision itself is authenticated: ``result``, ``reasons``, times, ``operation_horizon`` ... are unsigned and
  unbound) and never establishes Registry-origin authority (no operational trust root exists; synthetic keys are mechanism tests only).
* ``registry_authenticated`` stays False and ``registry_origin`` stays ``registry_origin_unverified`` in every output (Architect ruling E-2).

TRUST INPUTS. Every field of ``RegistryEvidenceTrust`` is supplied by the operator; none is ever read from the bundle. Replay cannot prove the operator derived them
independently of the record under test.

Refusals are ``ImportContractError`` with the typed codes below; every refusal is fail-closed (no bundle, no admission marker, no downgrade to structural-only or to
the caller-trusted digest match).
"""
from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from .instants import parse_instant
from .reconstruction import canonical_bytes

#: The one selector value that enables the profile (``type is str`` and exact equality; no prefix, wildcard, case folding or "latest").
REGISTRY_AUTHENTICATED_SELECTION_PROFILE = "registry-authenticated-selection/0.1"
#: Adapter profile id of the produced bundle. Deliberately NOT suffixed with the b19c47dd label (E-6): the record may come from changed Control Plane code and the
#: operator declares the actual source revisions in the trust object; Replay attests neither.
BOUNDED_CUR_REGISTRY_AUTHENTICATED_PROFILE = "control-plane-current-stack-registry-authenticated-selection-0.1@operator-declared-revision"

EVIDENCE_VERSION = "selection-evidence/0.1"
REQUEST_CONTRACT = "registry-evidence-verification-request/0.1"
VERDICT_CONTRACT = "registry-evidence-verdict/0.1"
BINDING_DOMAIN = "cognous.replay.registry-evidence-admission/0.1"
MAX_EVIDENCE_TEXT_BYTES = 65536
TIME_NOW_TOLERANCE_SECONDS = 300
TIME_MODES = ("now", "as_of")
EVIDENCE_KEYS = ("version", "contract_version", "family", "operation_id", "verified_at", "record_text", "selection_text")
#: PoC: F4 only (its host values are recoverable from ``members.f4_scalars``; non-F4 families persist only profile digests).
EVIDENCE_FAMILIES = {"f4": {"family_id": "f4-control-plane-age-bounds", "registry_contract": "r08-v2", "slot": "f4_ages"}}
FAMILY_ID_TO_SHORT = {v["family_id"]: k for k, v in EVIDENCE_FAMILIES.items()}
LAYERS_V2 = ("structural", "integrity", "record_binding", "trust_snapshot", "authenticity", "authority", "scope", "time", "revocation", "epoch", "disposition")
LAYER_VALUES = ("pass", "refuse", "not_evaluated")
VERDICT_KEYS = ("contract", "ok", "code", "authenticated", "layers", "family", "registry_contract", "selection_text_sha256", "record_text_sha256",
                "verification_time_utc", "trust_snapshot_id", "trust_snapshot_version", "trust_snapshot_fingerprint", "floors_applied", "epoch_floor_applied",
                "issuer_id", "selection_id", "epoch", "selection_digest", "bound_record_digest", "effective_policy_digest", "effective_values", "verifier_implementation")
HOST_AGE_KEYS = ("status_max_age_seconds", "approval_max_age_seconds")
SCALAR_MAX = 2147483647

MARKER_SELECTION_VERIFICATION = "admitted_by_operator_supplied_verifier_replay_holds_no_crypto"
MARKER_CLAIM = "A_selection_signature_per_injected_verifier"
MARKER_SNAPSHOT_ATTESTATION = "operator_supplied_unattested"
MARKER_SCOPE = "decision_time_only"
MARKER_REVISION_ATTESTATION = "operator_declared_unattested"
MARKER_VERIFIED_CLAIMS = ["selection_signature_by_snapshot_key", "record_binding", "issuer_grant_scope_operation", "time_window_at_T", "snapshot_floors_if_supplied",
                          "effective_policy_digest_matches_signed_bound_over_operator_host_ages"]
MARKER_NOT_VERIFIED = ["verifier_genuineness", "cp_decision_fields_not_covered_by_signature", "action_id_not_in_signed_statement", "selection_is_latest",
                       "effect_time_validity", "snapshot_correctness_independence", "substitution_by_other_genuine_selection", "real_world_issuer_identity"]
CLAIM_SCOPE_NOTE = ("mechanism verified with synthetic keys; Registry-origin authority not established; claim B not made; decision-time only; "
                    "operator trust inputs independence unverified")
#: Every metadata key the success path adds beyond the structural ones. Nothing else is ever written, and none of them exists in any other mode.
SUCCESS_MARKER_KEYS = frozenset({
    "control_plane_profile", "effective_configuration_verification", "registry_authenticated", "registry_origin", "registry_selection_verification",
    "registry_selection_admitted_by_injected_verifier", "registry_authentication_claim", "control_plane_decision_authenticated", "registry_trust_snapshot_attestation",
    "registry_trust_snapshot_id", "registry_trust_snapshot_version", "registry_floors_applied", "registry_verified_as_of", "registry_verified_time_mode",
    "registry_verified_scope", "registry_verified_claims", "registry_not_verified", "registry_declared_source_revisions", "registry_evidence", "claim_scope_note",
})

_HEX40 = re.compile(r"\A[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_DIGEST = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_CODE_SUFFIX = re.compile(r"\A[a-z0-9_]{1,64}\Z")


def _utc_now() -> datetime:
    """The operator's real UTC clock (module-level so tests can pin it)."""
    return datetime.now(timezone.utc)


def _refuse(code: str, message: str):
    from .importers import ImportContractError  # lazy: importers imports this module at load time
    raise ImportContractError(message, code=code)


# ----------------------------------------------------------------------------------------------------------------------------------- scalar predicates
def _text(v: Any, *, limit: int = 256) -> bool:
    """Non-empty exact ``str`` (no subclass), printable, UTF-8 encodable, bounded."""
    if type(v) is not str or not v or len(v) > limit or not v.isprintable():
        return False
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _token(v: Any) -> bool:
    return _text(v, limit=128) and not any(c.isspace() for c in v) and "*" not in v


def _int(v: Any, lo: int, hi: int = SCALAR_MAX) -> bool:
    return type(v) is int and lo <= v <= hi


# ----------------------------------------------------------------------------------------------------------------------------------- the trust object
class RegistryEvidenceVerifier(Protocol):
    """What the enforcing consumer injects. Constructed by the operator from pinned Registry code (``registry_successor.v2_verified_selection.RegistryEvidenceVerifierV2``);
    Replay cannot tell it from a stub. ``request`` is the plain dict built by ``build_request``; the return value must be the closed verdict dict."""
    def verify_selection_evidence(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


@dataclass(frozen=True, kw_only=True)
class RegistryExpectedContext:
    """Plain mirror of the Registry ExpectedContext (Replay imports nothing from the Registry). Operator-supplied; never read from the record."""
    consumer_id: str
    tenant: str
    institution: str
    authority_domain: str
    operation: str


@dataclass(frozen=True, kw_only=True)
class RegistryTrustSnapshotRef:
    """What the OPERATOR says the trust snapshot is; the verdict must echo it. The snapshot itself is opaque to Replay."""
    snapshot_id: str
    version: int


@dataclass(frozen=True, kw_only=True)
class RegistryEvidenceTrust:
    """Operator-supplied, record-independent trust inputs of the authenticated profile. Every field is mandatory except ``required_families`` and
    ``last_accepted_snapshot``. Validated at construction AND again (exact types, single read of every attribute) at the start of every import, because a frozen
    dataclass can still be built with ``object.__new__``/``object.__setattr__``."""
    verifier: Any = field(repr=False)
    trust_snapshot: Any = field(repr=False)
    trust_snapshot_ref: RegistryTrustSnapshotRef
    expected_context: RegistryExpectedContext
    expected_action_id: str
    expected_operation_id: str
    verification_time: datetime
    time_mode: str
    min_trust_snapshot_version: int
    expected_host_ages: Mapping[str, int]
    control_plane_source_revision: str
    registry_source_revision: str
    required_families: frozenset = frozenset({"f4"})
    last_accepted_snapshot: tuple | None = None

    def __post_init__(self) -> None:
        validate_trust(self)


_TRUST_FIELDS = ("verifier", "trust_snapshot", "trust_snapshot_ref", "expected_context", "expected_action_id", "expected_operation_id", "verification_time", "time_mode",
                 "min_trust_snapshot_version", "expected_host_ages", "control_plane_source_revision", "registry_source_revision", "required_families", "last_accepted_snapshot")
_CONTEXT_FIELDS = ("consumer_id", "tenant", "institution", "authority_domain", "operation")
_BAD_VERIFIER_TYPES = (Mapping, str, bytes, bytearray, bool, int, float, list, tuple, set, frozenset, os.PathLike, type)


@dataclass(frozen=True)
class ValidatedTrust:
    """Private snapshot of a validated trust object. Everything Replay later uses comes from here, never from the caller's object again."""
    verify: Any = field(repr=False)
    trust_snapshot: Any = field(repr=False)
    snapshot_id: str
    snapshot_version: int
    context: tuple  # (consumer_id, tenant, institution, authority_domain, operation)
    action_id: str
    operation_id: str
    time_utc: datetime
    time_utc_text: str
    time_mode: str
    min_version: int
    last_accepted: tuple | None
    host_ages: tuple  # (status_max_age_seconds, approval_max_age_seconds)
    cp_revision: str
    registry_revision: str


def validate_trust(trust: Any) -> ValidatedTrust:
    """Validate ``trust`` once and return a private snapshot. Raises ``registry_evidence_trust_missing`` for ``None``, ``registry_evidence_trust_malformed`` for anything
    else wrong, ``registry_evidence_family_set_mismatch`` for a well formed ``required_families`` that is not exactly {"f4"}, and
    ``registry_evidence_time_inconsistent`` for ``time_mode == "now"`` with an operator time more than 300 s from the real UTC clock."""
    if trust is None:
        _refuse("registry_evidence_trust_missing", "registry_evidence_trust was passed as None")
    if type(trust) is not RegistryEvidenceTrust:
        _refuse("registry_evidence_trust_malformed", "registry_evidence_trust must be exactly a RegistryEvidenceTrust")

    def bad(why: str):
        _refuse("registry_evidence_trust_malformed", "registry_evidence_trust invalid (" + why + ")")

    values = {}
    for name in _TRUST_FIELDS:  # single read of every attribute
        try:
            values[name] = getattr(trust, name)
        except Exception:
            bad("attribute " + name + " unreadable")
    verifier = values["verifier"]
    if verifier is None or isinstance(verifier, _BAD_VERIFIER_TYPES):
        bad("verifier")
    try:
        verify = getattr(verifier, "verify_selection_evidence")
    except Exception:
        bad("verifier")
    if not callable(verify):
        bad("verifier")
    if values["trust_snapshot"] is None:
        bad("trust_snapshot")
    ref = values["trust_snapshot_ref"]
    if type(ref) is not RegistryTrustSnapshotRef:
        bad("trust_snapshot_ref")
    try:
        ref_id, ref_version = ref.snapshot_id, ref.version
    except Exception:
        bad("trust_snapshot_ref")
    if not _token(ref_id) or not _int(ref_version, 1):
        bad("trust_snapshot_ref")
    ctx = values["expected_context"]
    if type(ctx) is not RegistryExpectedContext:
        bad("expected_context")
    try:
        context = tuple(getattr(ctx, n) for n in _CONTEXT_FIELDS)
    except Exception:
        bad("expected_context")
    if not all(_token(v) for v in context):
        bad("expected_context")
    if not _token(values["expected_action_id"]):
        bad("expected_action_id")
    if not _token(values["expected_operation_id"]):
        bad("expected_operation_id")
    if context[4] != values["expected_operation_id"]:
        bad("expected_context.operation differs from expected_operation_id")
    when = values["verification_time"]
    if type(when) is not datetime or when.tzinfo is None or when.utcoffset() is None:
        bad("verification_time must be a timezone-aware datetime")
    when_utc = when.astimezone(timezone.utc).replace(microsecond=0)  # the Registry works in whole seconds
    mode = values["time_mode"]
    if type(mode) is not str or mode not in TIME_MODES:
        bad("time_mode")
    if not _int(values["min_trust_snapshot_version"], 1):
        bad("min_trust_snapshot_version")
    last = values["last_accepted_snapshot"]
    if last is not None:
        if type(last) is not tuple or len(last) != 2 or not _int(last[0], 1) or not _text(last[1], limit=512):
            bad("last_accepted_snapshot")
    ages = values["expected_host_ages"]
    if type(ages) is not dict or set(ages) != set(HOST_AGE_KEYS) or not all(type(k) is str for k in ages) or not all(_int(ages[k], 1) for k in HOST_AGE_KEYS):
        bad("expected_host_ages")
    for name in ("control_plane_source_revision", "registry_source_revision"):
        if type(values[name]) is not str or _HEX40.match(values[name]) is None:
            bad(name)
    families = values["required_families"]
    if type(families) is not frozenset or not families or not all(type(f) is str for f in families):
        bad("required_families")
    if families != frozenset(EVIDENCE_FAMILIES):
        _refuse("registry_evidence_family_set_mismatch", "required_families is not exactly the supported family set")
    if mode == "now" and abs(_utc_now() - when_utc) > timedelta(seconds=TIME_NOW_TOLERANCE_SECONDS):
        _refuse("registry_evidence_time_inconsistent", "verification_time differs from the real UTC clock by more than 300 seconds in time_mode now")
    return ValidatedTrust(
        verify=verify, trust_snapshot=values["trust_snapshot"], snapshot_id=ref_id, snapshot_version=ref_version, context=context,
        action_id=values["expected_action_id"], operation_id=values["expected_operation_id"], time_utc=when_utc,
        time_utc_text=when_utc.strftime("%Y-%m-%dT%H:%M:%SZ"), time_mode=mode, min_version=values["min_trust_snapshot_version"],
        last_accepted=None if last is None else (last[0], last[1]), host_ages=tuple(ages[k] for k in HOST_AGE_KEYS),
        cp_revision=values["control_plane_source_revision"], registry_revision=values["registry_source_revision"])


# ----------------------------------------------------------------------------------------------------------------------------------- evidence shape
def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_text_ok(v: Any) -> bool:
    if type(v) is not str or not v:
        return False
    try:
        return len(v.encode("utf-8")) <= MAX_EVIDENCE_TEXT_BYTES
    except UnicodeEncodeError:  # lone surrogate: unrepresentable, a typed refusal, never an exception
        return False


def _check_evidence_shape(ev: Any) -> dict:
    """The single C2 object, closed. Returns it or raises ``selection_evidence_malformed`` / ``registry_evidence_family_set_mismatch``."""
    def bad(why: str):
        _refuse("selection_evidence_malformed", "selection_evidence malformed (" + why + ")")
    if type(ev) is not dict:
        bad("not a single object")
    if set(ev) != set(EVIDENCE_KEYS) or not all(type(k) is str for k in ev):
        bad("member set")
    if ev["version"] != EVIDENCE_VERSION or type(ev["version"]) is not str:
        bad("version")
    for name in ("contract_version", "family", "operation_id", "verified_at"):
        if type(ev[name]) is not str or not ev[name]:
            bad(name)
    if not _text(ev["operation_id"], limit=128):
        bad("operation_id")
    stamp = parse_instant(ev["verified_at"])
    if stamp is None or stamp.utcoffset() != timedelta(0):
        bad("verified_at")
    for name in ("record_text", "selection_text"):
        if not _evidence_text_ok(ev[name]):
            bad(name + " absent, not a str, unencodable or over " + str(MAX_EVIDENCE_TEXT_BYTES) + " UTF-8 bytes")
    if ev["family"] not in FAMILY_ID_TO_SHORT or ev["contract_version"] != EVIDENCE_FAMILIES[FAMILY_ID_TO_SHORT[ev["family"]]]["registry_contract"]:
        _refuse("registry_evidence_family_set_mismatch", "selection_evidence family or registry contract is not a supported one")
    return ev


# ----------------------------------------------------------------------------------------------------------------------------------- request / verdict
def build_request(ev: dict, tr: ValidatedTrust, host: Mapping[str, int]) -> dict:
    """The plain in-process request (never serialised). ``host`` is the operator's ``expected_host_ages``, never the record's values."""
    return {
        "contract": REQUEST_CONTRACT,
        "family": ev["family"],
        "registry_contract": ev["contract_version"],
        "selection_text": ev["selection_text"],
        "record_text": ev["record_text"],
        "expected_context": dict(zip(_CONTEXT_FIELDS, tr.context)),
        "expected_operation_id": tr.operation_id,
        "trust_snapshot": tr.trust_snapshot,
        "verification_time": tr.time_utc,
        "verification_time_utc": tr.time_utc_text,
        "min_trust_snapshot_version": tr.min_version,
        "last_accepted_snapshot": None if tr.last_accepted is None else [tr.last_accepted[0], tr.last_accepted[1]],
        "host_policy": {k: host[k] for k in HOST_AGE_KEYS},
    }


def _digest_like(v: Any) -> bool:
    return type(v) is str and (_DIGEST.match(v) is not None or _HEX64.match(v) is not None)


def _sha_equal(claimed: Any, actual_hex: str) -> bool:
    """Exact-string equality with the plain lowercase 64-hex SHA-256 of the UTF-8 text (Lead clarification of the frozen wire: no ``sha256:`` prefix)."""
    return type(claimed) is str and claimed == actual_hex


def check_verdict(verdict: Any, request: Mapping[str, Any], tr: ValidatedTrust, row_digest: str, f4_scalars: Mapping[str, int]) -> dict:
    """Closed verdict gate. Returns the verified members Replay records, or raises a typed refusal. Nothing here grants admission from the verdict's mere shape:
    the verdict is trusted only as far as the injected verifier is (NF-2)."""
    def malformed(why: str):
        _refuse("registry_evidence_verdict_malformed", "verdict malformed (" + why + ")")
    if type(verdict) is not dict:
        malformed("not a plain dict")
    ok = verdict.get("ok")
    if ok is False:
        code = verdict.get("code")
        if type(code) is not str or _CODE_SUFFIX.match(code) is None:
            malformed("refusal code")
        if code == "verifier_unavailable":
            _refuse("registry_evidence_verifier_unavailable", "verifier unavailable (BLOCKED: nothing admitted, no fallback)")
        _refuse("registry_evidence_unverified:" + code, "the verifier refused the selection evidence")
    if ok is not True:
        malformed("ok is not a bool")
    if set(verdict) != set(VERDICT_KEYS) or not all(type(k) is str for k in verdict):
        malformed("member set")
    layers = verdict["layers"]
    if verdict["contract"] != VERDICT_CONTRACT or type(verdict["contract"]) is not str:
        malformed("contract")
    if type(verdict["authenticated"]) is not bool or type(layers) is not dict or set(layers) != set(LAYERS_V2):
        malformed("authenticated/layers")
    if not all(type(v) is str and v in LAYER_VALUES for v in layers.values()):
        malformed("layer value")
    if verdict["code"] is not None and (type(verdict["code"]) is not str or _CODE_SUFFIX.match(verdict["code"]) is None):
        malformed("code")
    if verdict["code"] is not None or verdict["authenticated"] is not True or any(layers[n] != "pass" for n in LAYERS_V2):
        _refuse("registry_evidence_not_authenticated", "verdict ok but not authenticated or a layer is not pass (all eleven must pass)")
    for name in ("family", "registry_contract"):
        if type(verdict[name]) is not str:
            malformed(name)
    for name in ("selection_text_sha256", "record_text_sha256", "verification_time_utc", "trust_snapshot_id", "trust_snapshot_fingerprint", "issuer_id", "selection_id"):
        if not _text(verdict[name], limit=512):
            malformed(name)
    if not _digest_like(verdict["selection_digest"]) or not _digest_like(verdict["bound_record_digest"]) or type(verdict["effective_policy_digest"]) is not str \
            or _DIGEST.match(verdict["effective_policy_digest"]) is None:
        malformed("digest member")
    if not _int(verdict["trust_snapshot_version"], 1) or not _int(verdict["epoch"], 1):
        malformed("snapshot version / epoch")
    floors = verdict["floors_applied"]
    if type(floors) is not dict or set(floors) != {"min_trust_snapshot_version", "last_accepted_snapshot"} or not all(type(v) is bool for v in floors.values()):
        malformed("floors_applied")
    if type(verdict["epoch_floor_applied"]) is not bool:
        malformed("epoch_floor_applied")
    values = verdict["effective_values"]
    if type(values) is not dict or set(values) != set(HOST_AGE_KEYS) or not all(_int(values[k], 0) for k in HOST_AGE_KEYS):
        malformed("effective_values")
    impl = verdict["verifier_implementation"]  # shape only: verifier-supplied free text is never echoed anywhere
    if type(impl) is not dict or set(impl) != {"name", "registry_revision"} or not all(_text(impl[k], limit=128) for k in impl):
        malformed("verifier_implementation")
    # echoes: the verifier was told, and says it checked, exactly what Replay sent
    echoes_ok = (
        _sha_equal(verdict["selection_text_sha256"], _sha256_text(request["selection_text"]))
        and _sha_equal(verdict["record_text_sha256"], _sha256_text(request["record_text"]))
        and verdict["family"] == request["family"] and verdict["registry_contract"] == request["registry_contract"]
        and verdict["verification_time_utc"] == request["verification_time_utc"]
        and verdict["trust_snapshot_id"] == tr.snapshot_id and verdict["trust_snapshot_version"] == tr.snapshot_version
        and floors == {"min_trust_snapshot_version": True, "last_accepted_snapshot": tr.last_accepted is not None})
    if not echoes_ok:
        _refuse("registry_evidence_input_echo_mismatch", "the verdict does not echo what Replay sent")
    if verdict["effective_policy_digest"] != row_digest:
        _refuse("registry_evidence_effective_digest_mismatch", "the recomputed effective-policy digest differs from the recorded f4_ages family row")
    if values != {k: f4_scalars[k] for k in HOST_AGE_KEYS}:
        _refuse("registry_evidence_effective_values_mismatch", "the verifier's effective values differ from the recorded f4_scalars")
    return verdict


def binding_digest(*, decision_id: str, ec: Mapping[str, Any], ev: Mapping[str, Any], verdict: Mapping[str, Any], tr: ValidatedTrust) -> str:
    """``admission_binding_digest``: a Replay-internal commitment (NOT an authenticator, NOT a signing input) over the exact Replay record the admission was made for.
    It covers the effective-configuration digest, the scope, the f4 scalars, the f4_ages family row, the SHA-256 of both carried texts (never the texts themselves) and the
    verdict's signed-material members. It deliberately excludes the verification time, snapshot reference and floors so an honest later re-verification (new T, newer
    snapshot) reproduces it, while a substituted selection/record, or any edit of the covered record members, changes it."""
    members = ec["members"]
    row = next(r for r in members["families"] if r["slot"] == EVIDENCE_FAMILIES["f4"]["slot"])
    body = {
        "domain": BINDING_DOMAIN, "decision_id": decision_id, "family": ev["family"], "effective_configuration_digest": ec["digest"], "scope": members["scope"],
        "f4_scalars": members["f4_scalars"], "family_row": row, "selection_text_sha256": _sha256_text(ev["selection_text"]),
        "record_text_sha256": _sha256_text(ev["record_text"]), "selection_digest": verdict["selection_digest"], "bound_record_digest": verdict["bound_record_digest"],
        "effective_policy_digest": verdict["effective_policy_digest"], "issuer_id": verdict["issuer_id"], "selection_id": verdict["selection_id"], "epoch": verdict["epoch"],
        "expected_context": dict(zip(_CONTEXT_FIELDS, tr.context)), "expected_action_id": tr.action_id, "expected_operation_id": tr.operation_id,
    }
    return "sha256:" + hashlib.sha256(canonical_bytes(body)).hexdigest()  # canonical_bytes sees hashes and ids only, never a carried text


# ----------------------------------------------------------------------------------------------------------------------------------- admission
def _configuration(decision: Mapping[str, Any]) -> dict | None:
    binding = decision.get("binding")
    authority = binding.get("runtime_authority") if isinstance(binding, dict) else None
    record = authority.get("effective_configuration") if isinstance(authority, dict) else None
    return record if type(record) is dict else None


def admit(decisions: Any, tr: ValidatedTrust) -> list[dict]:
    """Admission algorithm. Called after the structural ``validate_run``/``check_run`` of the same import. Returns one record per authorized decision (the marker's
    ``registry_evidence`` list) or raises. The verifier is called only after every cheap refusal has passed, once per authorized decision."""
    rows = [d for d in decisions if isinstance(d, dict)] if type(decisions) is list else []
    authorized: list[tuple[dict, dict]] = []
    for d in rows:
        present = "selection_evidence" in d
        if d.get("result") != "authorized":
            if present:
                _refuse("undeclared_member", "selection_evidence is admitted only on authorized decisions")
            continue
        if not present:
            _refuse("selection_evidence_missing", "an authorized decision carries no selection_evidence")
        authorized.append((d, _check_evidence_shape(d["selection_evidence"])))
    if not authorized:
        _refuse("selection_evidence_missing", "no authorized decision carries selection_evidence")
    if frozenset(FAMILY_ID_TO_SHORT[ev["family"]] for _, ev in authorized) != frozenset(EVIDENCE_FAMILIES):
        _refuse("registry_evidence_family_set_mismatch", "the evidence family set differs from the required family set")
    prepared = []
    for d, ev in authorized:
        ec = _configuration(d)
        if ec is None:
            _refuse("registry_evidence_family_set_mismatch", "the decision carries no effective_configuration")
        members = ec["members"]
        row = next((r for r in members["families"] if r["slot"] == EVIDENCE_FAMILIES["f4"]["slot"]), None)
        if row is None:
            _refuse("registry_evidence_family_set_mismatch", "the effective_configuration has no f4_ages family row")
        scope = members["scope"]
        consumer, tenant, institution, domain, _operation = tr.context
        if (scope["consumer_id"], scope["tenant_id"], scope["institution_id"], scope["authority_domain"], scope["action_id"]) != (consumer, tenant, institution, domain, tr.action_id) \
                or d["binding"].get("tenant_id") != tenant or d["binding"].get("action_id") != tr.action_id or ev["operation_id"] != tr.operation_id:
            _refuse("registry_evidence_scope_mismatch", "the operator context differs from the record scope (consumer, tenant, institution, authority_domain, action, operation)")
        prepared.append((d, ev, ec, row))
    result = []
    for d, ev, ec, row in prepared:
        members = ec["members"]
        host = dict(zip(HOST_AGE_KEYS, tr.host_ages))
        request = build_request(ev, tr, host)
        try:
            verdict = tr.verify(request)
        except Exception:
            _refuse("registry_evidence_verifier_error", "the verifier raised")
        checked = check_verdict(verdict, request, tr, row["effective_policy_digest"], members["f4_scalars"])
        decision_id = d.get("decision_id")
        result.append({
            "decision_id": decision_id, "family": ev["family"], "registry_contract": ev["contract_version"], "issuer_id": checked["issuer_id"],
            "selection_id": checked["selection_id"], "epoch": checked["epoch"], "selection_digest": checked["selection_digest"],
            "bound_record_digest": checked["bound_record_digest"], "effective_policy_digest": checked["effective_policy_digest"],
            "trust_snapshot_fingerprint": checked["trust_snapshot_fingerprint"], "epoch_floor_applied": checked["epoch_floor_applied"],
            "admission_binding_digest": binding_digest(decision_id=decision_id, ec=ec, ev=ev, verdict=checked, tr=tr),
        })
    return result


def success_markers(tr: ValidatedTrust, admissions: list[dict]) -> dict:
    """Metadata of a successful authenticated-profile import (and only of that). ``registry_authenticated`` stays False and ``registry_origin`` stays unverified."""
    return {
        "control_plane_profile": REGISTRY_AUTHENTICATED_SELECTION_PROFILE,
        "effective_configuration_verification": "internal_consistency_only_registry_source_revision_unverified",
        "registry_authenticated": False,
        "registry_origin": "registry_origin_unverified",
        "registry_selection_verification": MARKER_SELECTION_VERIFICATION,
        "registry_selection_admitted_by_injected_verifier": True,
        "registry_authentication_claim": MARKER_CLAIM,
        "control_plane_decision_authenticated": False,
        "registry_trust_snapshot_attestation": MARKER_SNAPSHOT_ATTESTATION,
        "registry_trust_snapshot_id": tr.snapshot_id,
        "registry_trust_snapshot_version": tr.snapshot_version,
        "registry_floors_applied": {"min_trust_snapshot_version": True, "last_accepted_snapshot": tr.last_accepted is not None},
        "registry_verified_as_of": tr.time_utc_text,
        "registry_verified_time_mode": "now" if tr.time_mode == "now" else "as_of_historical",
        "registry_verified_scope": MARKER_SCOPE,
        "registry_verified_claims": list(MARKER_VERIFIED_CLAIMS),
        "registry_not_verified": list(MARKER_NOT_VERIFIED),
        "registry_declared_source_revisions": {"control_plane": tr.cp_revision, "registry": tr.registry_revision, "attestation": MARKER_REVISION_ATTESTATION},
        "registry_evidence": [dict(a) for a in admissions],
        "claim_scope_note": CLAIM_SCOPE_NOTE,
    }


# ----------------------------------------------------------------------------------------------------------------------------------- retained bundles
def reverify_retained_registry_evidence(bundle: Any, *, registry_evidence_trust: Any, proposal: dict | None = None):
    """Re-run the FULL authenticated admission over a retained bundle with trust the operator supplies NOW.

    The selector and profile are hard-coded here and the Control Plane format label is the module constant; NOTHING in the bundle's metadata (``control_plane_profile``,
    ``registry_selection_admitted_by_injected_verifier``, ``registry_evidence`` ...) is used as input. The retained ``registry_evidence[*].admission_binding_digest`` values
    are compared (as data) with the freshly recomputed ones: a difference, or a different decision set, is ``registry_evidence_binding_mismatch``. A bundle with no stored
    values is simply verified afresh. Returns the fresh bundle whose markers come from this call."""
    from .importers import CONTROL_PLANE_CUR_REVISION, import_bounded_workflow
    from .refusal_evidence import extend_retained_inputs
    dumped = bundle.model_dump(mode="json") if hasattr(bundle, "model_dump") else bundle
    if not isinstance(dumped, Mapping) or not isinstance(dumped.get("records"), list) or not all(isinstance(r, Mapping) for r in dumped["records"]):
        _refuse("schema_violation", "retained bundle is not a reconstruction bundle")
    records = sorted(dumped["records"], key=lambda r: r.get("source_sequence", 0))

    def by(kind: str) -> list:
        return [r.get("data") for r in records if r.get("record_type") == kind]
    run_id = dumped.get("run_id")
    rebuilt = extend_retained_inputs({"run_id": run_id, "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
                                      "observations": by("effect_observation"), "reconciliations": by("reconciliation")}, dumped)
    retained_proposal = by("runtime_proposal")
    fresh = import_bounded_workflow(rebuilt, proposal=proposal if proposal is not None else (retained_proposal[0] if len(retained_proposal) == 1 else None),
                                    control_plane_revision=CONTROL_PLANE_CUR_REVISION, control_plane_profile=REGISTRY_AUTHENTICATED_SELECTION_PROFILE,
                                    registry_evidence_trust=registry_evidence_trust)
    stored = (dumped.get("metadata") or {}).get("registry_evidence") if isinstance(dumped.get("metadata"), Mapping) else None
    if stored is not None:
        recomputed = {e["decision_id"]: e["admission_binding_digest"] for e in fresh.metadata["registry_evidence"]}
        kept = None
        if isinstance(stored, list) and all(isinstance(e, Mapping) for e in stored):
            kept = {e.get("decision_id"): e.get("admission_binding_digest") for e in stored}
        if kept != recomputed or (isinstance(stored, list) and len(stored) != len(recomputed)):
            _refuse("registry_evidence_binding_mismatch", "the retained admission_binding_digest differs from the recomputed one")
    return fresh
