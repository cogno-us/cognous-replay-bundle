"""Registry-governed effective-configuration profile (``registry-governed-effective-configuration/0.1``).

Admission of ``binding.runtime_authority.effective_configuration`` for ONE explicitly selected profile and nothing else. The member is produced by the Control Plane
``b19c47ddd020409d24e52e70b11359c46265edbb`` (``agent_control_plane/effective_configuration_binding.py``, version ``effective-configuration-binding/0.1``) on every
AUTHORIZED decision of a Registry-governed workflow. This module is a pure re-implementation of that producing contract (no Control Plane import, no new dependency); it is
cross-checked against digests recorded from the real Control Plane in ``tests/test_registry_governed_effective_configuration.py``.

What a pass establishes: the member has exactly the frozen shape, every value is inside its structural domain, ``digest`` is the recomputation over the domain, the version and
the member's own ``members``, the family rows are the Control Plane family table (slot, family id, Registry contract version, schema revision, composition order), the scope
agrees with the decision's ``binding.action_id`` and ``binding.tenant_id`` and (when a proposal is supplied) with the proposal's ``tenant_id`` and ``action_id``, ``effective_profile_digest`` equals the
decision's ``catalogue_digest`` when not null, the member is present on every authorized decision and on no other, and one run carries one configuration.

Explicit, tested non-detections (no decision field carries them and the record holds no input to recompute them): scope.institution_id, scope.consumer_id and
scope.authority_domain; host_profile_digest; every family effective_policy_digest (Registry material is not in the record); and effective_profile_digest when it is null (the
tie to catalogue_digest then does not exist; a non-null value cannot be recomputed from family digests, it is a hash of the profile). A resealed edit of any of these passes.
"Stale" is covered only by the effective_profile_digest == catalogue_digest tie: there is no time or revision binding.

Optional CALLER-TRUSTED MATCH (``import_bounded_workflow(..., expected_effective_configuration_digest=...)``, fail-closed once the parameter is passed at all): after every check above, the record digest must equal a
digest the caller supplies independently of the record; this detects a resealed substitution but only as far as the caller's source is trusted, and Replay cannot tell where the string came from.

What it does NOT establish (stated, never inferred): that the configuration is the one in force, that the Registry material was genuine or at which Registry revision
(neither is carried in the record), that a signature or trust snapshot was verified, or that the Control Plane or the Registry is qualified. BUILDER_TESTED upstream; the
digest is a redundant self-consistency commitment over unsigned local JSON, not an authenticator.
"""
from __future__ import annotations

import re
from typing import Any

from .reconstruction import canonical_bytes
import hashlib

#: The one selector value that enables the profile (exact string equality; no prefix, wildcard, case folding or "latest").
REGISTRY_GOVERNED_PROFILE = "registry-governed-effective-configuration/0.1"
KEY = "effective_configuration"
VERSION = "effective-configuration-binding/0.1"
DOMAIN = "cognous.control-plane.effective-configuration-binding"
SCALAR_MAX = 2147483647
RECORD_FIELDS = ("version", "digest", "members")
MEMBER_FIELDS = ("scope", "host_profile_digest", "effective_profile_digest", "f4_scalars", "other_scalars", "observation_policy", "families")
SCOPE_FIELDS = ("consumer_id", "tenant_id", "action_id", "institution_id", "authority_domain")
F4_FIELDS = ("status_max_age_seconds", "approval_max_age_seconds")
OTHER_FIELDS = ("clock_tolerance_seconds", "identity_max_age_seconds", "mandate_max_age_seconds")
OBSERVATION_FIELDS = ("max_age_seconds", "clock_tolerance_seconds")
FAMILY_FIELDS = ("slot", "family_id", "contract_version", "family_schema_revision", "effective_policy_digest")
#: Control Plane b19c47dd registry_effective_policy.FAMILY_TABLE / SCHEMA_REVISIONS / registry_governed_policy.FAMILY_NAMES (composition order).
FAMILY_ORDER = ("f4_ages", "class_age", "class_unreadable", "class_revocation_assurance", "class_irreversible", "anchor_deadline", "observation_max_age",
                "observation_clock_tolerance", "terminal_revocation")
FAMILY_TABLE = {
    "f4_ages": ("f4-control-plane-age-bounds", "r08-v2"),
    "class_age": ("f5-action-class-age-bounds", "r08-v2"),
    "class_unreadable": ("f5-action-class-unreadable-policy", "r08-v5"),
    "class_revocation_assurance": ("f5-action-class-revocation-assurance-policy", "r08-v6"),
    "class_irreversible": ("f5-action-class-irreversibility-policy", "r08-v7"),
    "anchor_deadline": ("f5-anchor-deadline-to-inputs-policy", "r08-v8"),
    "observation_max_age": ("f5-observation-max-age-policy", "r08-v8"),
    "observation_clock_tolerance": ("f5-observation-clock-tolerance-policy", "r08-v8"),
    "terminal_revocation": ("f5-terminal-revocation-enablement-policy", "r08-v6"),
}
SCHEMA_REVISIONS = {"class_irreversible": 1, "anchor_deadline": 1, "observation_max_age": 1, "observation_clock_tolerance": 1}
_DIGEST = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_ZERO = "sha256:" + "0" * 64


def _scalar(v: Any) -> bool:
    return type(v) is int and 0 <= v <= SCALAR_MAX


def _text(v: Any) -> bool:
    return type(v) is str and bool(v)


def _digest(v: Any) -> bool:
    return type(v) is str and _DIGEST.match(v) is not None and v != _ZERO


def _optional_digest(v: Any) -> bool:
    return v is None or _digest(v)


def _exact(d: Any, fields: tuple) -> bool:
    return type(d) is dict and set(d) == set(fields) and all(type(k) is str for k in d)


def digest_of(version: str, members: dict) -> str:
    """Control Plane ``commitment({"domain": DOMAIN, "version": version, **members})``: sha256 of the sorted-key, compact, ensure_ascii=False canonical JSON."""
    return "sha256:" + hashlib.sha256(canonical_bytes({"domain": DOMAIN, "version": version, **members})).hexdigest()


def members_defect(members: Any) -> str | None:
    """None when ``members`` has exactly the Control Plane shape and every value is in its structural domain, else a short diagnostic."""
    if not _exact(members, MEMBER_FIELDS):
        return "members_shape"
    if not _exact(members["scope"], SCOPE_FIELDS) or not all(_text(v) for v in members["scope"].values()):
        return "scope"
    if not _optional_digest(members["host_profile_digest"]) or not _optional_digest(members["effective_profile_digest"]):
        return "profile_digest"
    for name, fields in (("f4_scalars", F4_FIELDS), ("other_scalars", OTHER_FIELDS)):
        if not _exact(members[name], fields) or not all(_scalar(v) for v in members[name].values()):
            return name
    obs = members["observation_policy"]
    if obs is not None and (not _exact(obs, OBSERVATION_FIELDS) or not all(_scalar(v) for v in obs.values())):
        return "observation_policy"
    families = members["families"]
    if type(families) is not list:
        return "families"
    last = -1
    for row in families:
        if not _exact(row, FAMILY_FIELDS) or not all(_text(row[k]) for k in ("slot", "family_id", "contract_version")) or not _digest(row["effective_policy_digest"]):
            return "families"
        slot = row["slot"]
        # The Control Plane family table: unknown slot, wrong family id / Registry contract version / schema revision, duplicate or out-of-order row are all unsupported.
        if slot not in FAMILY_TABLE or (row["family_id"], row["contract_version"]) != FAMILY_TABLE[slot]:
            return "families"
        revision = row["family_schema_revision"]
        if revision != SCHEMA_REVISIONS.get(slot) or (revision is not None and type(revision) is not int):
            return "families"
        position = FAMILY_ORDER.index(slot)
        if position <= last:
            return "families"
        last = position
    return None


def record_defect(record: Any) -> str | None:
    """None for a well formed, internally consistent member of the supported version, else why not."""
    if type(record) is not dict or type(record.get("version")) is not str:
        return "invalid:record"
    if record["version"] != VERSION:
        return "version_unsupported"
    if not _exact(record, RECORD_FIELDS):
        return "invalid:record"
    if not _digest(record["digest"]):
        return "invalid:digest"
    defect = members_defect(record["members"])
    if defect is not None:
        return "invalid:" + defect
    if digest_of(record["version"], record["members"]) != record["digest"]:
        return "invalid:digest_mismatch"
    return None


def expected_defect(expected: Any) -> str | None:
    """None when a caller-supplied expected digest is well formed (same predicate as the Control Plane: exact ``sha256:`` + 64 lowercase hex, not all zero), else the typed reason."""
    if expected is None:
        return "effective_configuration_expected_missing"
    return None if _digest(expected) else "effective_configuration_expected_malformed"


def check_run(decisions: list, proposal: Any, refuse, expected: str | None = None) -> None:
    """Run-level checks for the selected profile. ``refuse(message, code=None)`` raises the importer's typed refusal. Called after the base member check, once per run.

    ``expected`` (already validated by ``expected_defect``; ``None`` = structural-only) is the caller-trusted digest. It is compared LAST, after the structure, the
    recomputed digest and every consistency check above have passed, so a mismatch refuses before any decision is accepted. CALLER-TRUSTED match only, not authentication."""
    configuration = None
    for d in decisions:
        binding = d.get("binding") or {}
        authority = binding.get("runtime_authority") if isinstance(binding, dict) else None
        authorized = d.get("result") == "authorized"
        present = isinstance(authority, dict) and KEY in authority
        if authorized and not present:
            refuse("effective_configuration is missing on an authorized decision (Registry-governed profile)", "schema_violation")
        if present and not authorized:
            refuse("effective_configuration present on a decision that is not authorized (the Control Plane mints it only on authorized decisions)", "undeclared_member")
        if not present:
            continue
        record = authority[KEY]
        defect = record_defect(record)
        if defect == "version_unsupported":
            refuse("effective_configuration version unsupported", "schema_violation")
        if defect is not None:
            refuse("effective_configuration invalid: " + defect, "schema_violation" if defect != "invalid:record" else "undeclared_member")
        scope = record["members"]["scope"]
        if scope["action_id"] != binding.get("action_id"):
            refuse("effective_configuration scope.action_id differs from the decision's binding.action_id", "schema_violation")
        # The decision's own binding carries tenant_id for every tenant-aware (Registry-governed) decision (bounded.py binding_extra); bind to it even without a proposal.
        if binding.get("tenant_id") != scope["tenant_id"]:
            refuse("effective_configuration scope.tenant_id differs from the decision's binding.tenant_id", "schema_violation")
        # The proposal comparison is the Control Plane's _gl_revalidate rule; its action_id half is redundant with the binding check above (kept as defence in depth).
        if isinstance(proposal, dict) and (proposal.get("tenant_id") != scope["tenant_id"] or proposal.get("action_id") != scope["action_id"]):
            refuse("effective_configuration scope differs from the proposal's tenant_id/action_id", "schema_violation")
        effective = record["members"]["effective_profile_digest"]
        if effective is not None and effective != authority.get("catalogue_digest"):
            refuse("effective_configuration.effective_profile_digest differs from catalogue_digest", "schema_violation")
        if configuration is None:
            configuration = record
        elif record != configuration:
            refuse("conflicting effective_configuration within one run (more than one configuration)", "schema_violation")
    if expected is not None:
        if configuration is None:
            refuse("no authorized decision carries effective_configuration; a caller-trusted match is impossible", "effective_configuration_record_missing")
        # configuration["digest"] was just verified equal to the recomputation over its own members (record_defect), and one run carries one configuration.
        if configuration["digest"] != expected:
            refuse("effective_configuration digest differs from the caller-trusted expected digest", "effective_configuration_expected_mismatch")
