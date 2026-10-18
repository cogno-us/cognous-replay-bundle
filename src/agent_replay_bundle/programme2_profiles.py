"""Programme-2 opt-in profile members of the Control Plane run record: acceptance, retention and damage refusal.

Three opt-in profiles of the Control Plane (host-governed settings of ``RuntimeAuthorityProfile``) add members to the
bounded run record. With a profile off none of its members appears and nothing in this module runs. With a profile on,
Replay accepts them only for the exact programme-2 Control Plane revision (``CONTROL_PLANE_P2_REVISION``); every earlier
generation keeps refusing or ignoring them exactly as before.

* operation identity ``operation-identity/0.1`` (N1): the lists ``operations``, ``operation_renewals``, ``attempt_joins``,
  ``operation_id``/``operation_issuer`` in a binding's ``runtime_authority``, ``check_id`` on effect-time refusals;
* rule revision ``rule-revision/0.1`` (N2): the lists ``rule_revisions``, ``rule_revision_refusals`` and ``rule_identity`` on
  decisions and refusals;
* freshness ``freshness/0.1`` (N3): the lists ``age_extensions``, ``age_extension_refusals``, ``recovery_runs``, the three
  clocks (``evaluated_at``/``recorded_at``) on decisions, attempts, refusals and resolution checks, ``deadline``,
  ``age_bound_seconds``, ``extension_id``, ``nonce`` and the phases ``overdue``/``expired`` on journal events,
  ``age_basis`` on inputs;
* merge record ``merge-record/0.1`` (N4): the lists ``merge_records``, ``compensation_obligations`` and ``merged_into`` on attempt
  joins (the folded operation of a merge dispatches under the survivor's id);
* reversibility ``reversibility/0.1`` (N4): the list ``snapshot_uses`` (a cached purpose snapshot used, or refused, during an
  outage) and the action-class member ``x-reversibility`` (free-form action class members are retained as written);
* dedupe ``dedupe-ttl/0.1`` (N4): the list ``dedupe_escalations`` and an attempt left ``unknown`` with ``error``
  ``destination_in_progress``.

The decision, refusal, check and journal rows of a run that used any code only the reason registry label
``runtime-authority-reasons/0.2`` registers carry that label instead of ``/0.1`` (the Control Plane stamps a row with 0.2 only for
such a code; 0.2 is a superset of 0.1). Replay accepts exactly those two labels for the programme-2 revision and does not check the
label against the codes (that is the verifier's job); any other label is refused as ``unknown_enum_value``.

The shapes were read from the producer's real output (control plane ``3755c71a``) and the ODES contracts
``operation-identity``, ``rule-revision`` and ``freshness-clocks`` (``0.1.0-draft``, not frozen); where they differ the
producer's output wins.

What this module checks: closed member sets (an undeclared member outside ``extensions`` is refused, never dropped), required
members, closed enumerations, timezone-aware times, the ``x-`` extension namespace, and the cross-row references and
couplings a retained record must still satisfy (a join names an attempt that exists, a deadline is the opening plus the bound,
an expired event has its refusal, an adopted rule identity has its revision row). It does not re-derive the producer's
decisions, does not verify any signer, and does not prove the profile was on: a record from which every profile member was
removed is indistinguishable from a profile-off record. Independent re-derivation belongs to the verifier.

Refusal codes are the ODES contract codes where a contract rule is applied (``undeclared_member``, ``schema_violation``,
``unknown_enum_value``, ``timestamp_invalid``, ``invalid_extension_key``, ``join_attempt_missing``, ``deadline_mismatch``, ...).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

REASON_LABELS = ("runtime-authority-reasons/0.1", "runtime-authority-reasons/0.2")

PROFILE_LISTS = {
    "operations": "operation",
    "operation_renewals": "operation_renewal",
    "attempt_joins": "attempt_join",
    "rule_revisions": "rule_revision",
    "rule_revision_refusals": "rule_revision_refusal",
    "age_extensions": "age_extension",
    "age_extension_refusals": "age_extension_refusal",
    "recovery_runs": "recovery_run",
    "merge_records": "merge_record",
    "compensation_obligations": "compensation_obligation",
    "snapshot_uses": "snapshot_use",
    "dedupe_escalations": "dedupe_escalation",
}

# Members a profile adds to rows Replay already knows (allowed only for the programme-2 revision).
ATTEMPT_PROFILE_MEMBERS = frozenset({"evaluated_at", "recorded_at"})

EXTENSION_NAME = re.compile(r"^x-[a-z0-9][a-z0-9._-]*$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
EXPIRED = "check_expired_before_dispatch"
OVERDUE = "check_overdue"
PHASES = frozenset({"opened", "input", "completed", "interrupted", "overdue", "expired"})

_RULE_STATES = ("adopted", "unknown")
_VERIFIED = ("none", "revision_row_present", "signer_independent_and_configured", "digest_matches_signed_revision")
# Row specs: member -> (kind, required). Kinds: str, str?, int, num, bool, time, time?, list, dict, ('enum', values), ('enum?', values), any.
_OPERATION = {"operation_id": ("str", 1), "principal_id": ("str", 1), "authority_domain": ("str", 1), "issuer": ("str", 1),
              "grant_id": ("str", 1), "first_grant_revision": ("str", 1), "admitted_at": ("time", 1), "evaluated_at": ("time", 0)}
_RENEWAL = {"renewal_id": ("str", 1), "operation_id": ("str", 1), "grant_id": ("str?", 1), "from_revision": ("str?", 1),
            "to_revision": ("str", 1), "written_by": ("str", 1),
            "outcome": (("enum", ("accepted", "refused")), 1),
            "refusal_code": (("enum?", ("operation_not_admitted", "renewal_not_written_by_grant_issuer", "renewal_revision_not_new")), 1),
            "recorded_at": ("time", 1), "evaluated_at": ("time", 0)}
_JOIN = {"join_id": ("str", 1), "operation_id": ("str", 1), "attempt_id": ("str", 1), "check_id": ("str", 1), "effect_id": ("str", 1),
         "decision_id": ("str", 1), "grant_id": ("str", 1), "grant_revision": ("str", 1), "resolver_id": ("str", 1),
         "resolver_version": ("str", 1), "class_max_age": ("int", 1), "expected_effective_grant_digest": ("str?", 1),
         "merged_into": ("str?", 1), "recorded_at": ("time", 1),
         "time_source": (("enum", ("control_plane", "test_override")), 1), "evaluated_at": ("time", 0)}
_REVISION = {"revision_id": ("str", 1), "rule_kind": (("enum", ("reason_registry", "policy", "gate_implementation",
                                                                   "merge_equivalence_rule")), 1),
             "rule_ref": ("str", 1), "from_digest": ("str?", 1), "to_digest": ("str", 1), "reviser": ("str", 1),
             "signer": ("str?", 1), "authority_ref": ("str?", 1), "reason": ("str", 1), "supersedes": ("str?", 1),
             "recorded_at": ("time", 1), "declared_arity": ("dict", 0)}
_REVISION_REFUSAL = {"refusal_id": ("str", 1), "revision": ("dict", 1), "reasons": ("list", 1), "recorded_at": ("time", 1)}
_EXTENSION = {"extension_id": ("str", 1), "class_id": ("str", 1), "from_max_age_seconds": ("int", 1),
              "to_max_age_seconds": ("int", 1), "not_before": ("time", 1), "expires_at": ("time", 1), "outage_ref": ("str", 1),
              "requested_by": ("str", 1), "signer": ("str?", 1), "authority_ref": ("str?", 1), "recorded_at": ("time", 1),
              "evaluated_at": ("time", 0)}
_EXTENSION_REFUSAL = {"refusal_id": ("str", 1), "extension": ("dict", 1), "reasons": ("list", 1), "recorded_at": ("time", 1)}
_RECOVERY_RUN = {"run_id": ("str", 1), "trigger": (("enum", ("startup", "interval", "manual")), 1), "recorded_at": ("time", 1),
                 "interrupted": ("list", 1), "overdue": ("list", 1), "open_count": ("int", 1),
                 "oldest_open_age_seconds": ("num?", 1)}
_MERGE_OUTCOMES = ("merged", "held", "unknown", "refused")
_MERGE = {"merge_id": ("str", 1), "survivor_operation_id": ("str", 1), "folded_operation_ids": ("list", 1),
          "equivalence_rule_ref": ("str", 1), "equivalence_rule_digest": ("str", 1),
          "rule_state": (("enum", _RULE_STATES), 1), "rule_verified_through": (("enum", _VERIFIED), 1), "rule_findings": ("list", 1),
          "merged_by": ("str", 1), "authority_ref": ("str?", 1), "reason": ("str", 1),
          "outcome": (("enum", _MERGE_OUTCOMES), 1), "reasons": ("list", 1), "compensation_obligation_id": ("str", 0),
          "recorded_at": ("time", 1), "evaluated_at": ("time", 0)}
_OBLIGATION = {"obligation_id": ("str", 1), "merge_id": ("str", 1), "survivor_operation_id": ("str", 1), "operation_ids": ("list", 1),
               "effect_ids": ("list", 1), "effect_ids_by_operation": ("dict", 1), "unresolved_effect_ids": ("list", 1),
               "status": (("enum", ("recorded",)), 1), "execution": (("enum", ("not_executed",)), 1),
               "recorded_at": ("time", 1), "evaluated_at": ("time", 0)}
_SNAPSHOT_USE = {"use_id": ("str", 1), "class_id": ("str", 1), "purpose_ref": ("str", 1), "check_id": ("str", 0),
                 "basis": (("enum", ("live_read", "cached_snapshot", "strict_default")), 1),
                 "effective_status": (("enum", ("open", "closed")), 1), "accepted": ("bool", 1),
                 "reversibility": (("enum", ("irreversible", "reversible_until", "reversible_at_cost")), 1),
                 "epoch": ("str?", 1), "snapshot_status": ("str?", 1), "snapshot_observed_at": ("time?", 1),
                 "age_seconds": ("num?", 1), "age_bound_seconds": ("int", 1), "extension_id": ("str", 0),
                 "age_basis": (("enum", ("source_asserted",)), 1), "reasons": ("list", 1), "recorded_at": ("time", 1),
                 "evaluated_at": ("time", 1)}
_ESCALATION = {"escalation_id": ("str", 1), "effect_id": ("str", 1), "operation_id": ("str?", 1),
               "mode": (("enum", ("none", "destination_ttl")), 1), "in_progress": ("bool", 1), "first_attempt_at": ("time", 1),
               "provider_horizon_at": ("time", 1), "escalation_deadline_at": ("time", 1), "key_expires_at": ("time", 1),
               "same_key_safe_until": ("time?", 1), "fired_at": ("time", 1), "fired_inside_key_ttl": ("bool", 1),
               "reasons": ("list", 1), "recorded_at": ("time", 1), "evaluated_at": ("time", 0)}
SPECS = {"operations": _OPERATION, "operation_renewals": _RENEWAL, "attempt_joins": _JOIN, "rule_revisions": _REVISION,
         "rule_revision_refusals": _REVISION_REFUSAL, "age_extensions": _EXTENSION, "age_extension_refusals": _EXTENSION_REFUSAL,
         "recovery_runs": _RECOVERY_RUN, "merge_records": _MERGE, "compensation_obligations": _OBLIGATION,
         "snapshot_uses": _SNAPSHOT_USE, "dedupe_escalations": _ESCALATION}
_FINDINGS = ("no_signed_revision", "unsigned_revision_row", "self_signed_revision_row", "signer_not_configured",
             "digest_mismatch_with_adopted", "observed_digest_absent")
_EXTENSION_REFUSAL_REASONS = ("age_extension_unsigned", "age_extension_self_signed", "age_extension_signer_not_configured",
                              "age_extension_exceeds_limit", "age_extension_invalid", "age_extension_authority_unconfigured")


def _error(message: str, code: str):
    from .importers import ImportContractError
    return ImportContractError("programme-2 profile: " + message, code)


def instant(value: Any, label: str) -> datetime:
    """A timezone-aware ISO-8601 time, else ``timestamp_invalid``."""
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError) as exc:
        raise _error(f"{label} is not an ISO-8601 time", "timestamp_invalid") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise _error(f"{label} has no UTC offset", "timestamp_invalid")
    return result


def _check_kind(value: Any, kind: Any, label: str) -> None:
    if isinstance(kind, tuple):
        nullable = kind[0] == "enum?"
        if value is None and nullable:
            return
        if not isinstance(value, str) or value not in kind[1]:
            raise _error(f"{label} is not a declared value: {value!r}", "unknown_enum_value")
        return
    if kind.endswith("?") and value is None:
        return
    base = kind.rstrip("?")
    ok = {"str": isinstance(value, str) and bool(value), "int": type(value) is int and value >= 0,
          "num": type(value) in (int, float) and value >= 0, "bool": type(value) is bool, "list": isinstance(value, list), "dict": isinstance(value, dict),
          "time": isinstance(value, str)}[base]
    if not ok:
        raise _error(f"{label} has the wrong type or range", "schema_violation")
    if base == "time":
        instant(value, label)


def check_extensions(raw: dict[str, Any], label: str) -> None:
    ext = raw.get("extensions")
    if ext is None and "extensions" not in raw:
        return
    if not isinstance(ext, dict):
        raise _error(f"{label}.extensions must be an object", "schema_violation")
    bad = sorted(str(k) for k in ext if not (isinstance(k, str) and EXTENSION_NAME.match(k)))
    if bad:
        raise _error(f"{label}.extensions names must start with 'x-': " + ",".join(bad), "invalid_extension_key")


def check_row(raw: Any, label: str, spec: dict[str, tuple[Any, int]]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise _error(f"{label} must be an object", "schema_violation")
    unknown = sorted(str(k) for k in set(raw) - set(spec) - {"extensions"})
    if unknown:
        raise _error(f"{label} has undeclared member(s): " + ",".join(unknown), "undeclared_member")
    for name, (kind, required) in spec.items():
        if name not in raw:
            if required:
                raise _error(f"{label}.{name} is required", "schema_violation")
            continue
        _check_kind(raw[name], kind, f"{label}.{name}")
    check_extensions(raw, label)
    return raw


def _rows(cp: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = cp.get(field, [])
    if not isinstance(value, list):
        raise _error(f"{field} must be an array", "schema_violation")
    return value


def _unique(rows: list[dict[str, Any]], key: str, code: str, label: str) -> None:
    seen: set[Any] = set()
    for row in rows:
        if row[key] in seen:
            raise _error(f"{label} {row[key]!r} is repeated", code)
        seen.add(row[key])


def _check_rule_identity(identity: Any, label: str) -> None:
    if not isinstance(identity, dict):
        raise _error(f"{label} must be an object", "schema_violation")
    if set(identity) - {"rules", "unknown"}:
        raise _error(f"{label} has undeclared member(s): " + ",".join(sorted(set(identity) - {"rules", "unknown"})), "undeclared_member")
    if set(identity) != {"rules", "unknown"}:
        raise _error(f"{label} requires rules and unknown", "schema_violation")
    rules, unknown = identity["rules"], identity["unknown"]
    if not isinstance(rules, dict) or not isinstance(unknown, list):
        raise _error(f"{label} rules/unknown have the wrong type", "schema_violation")
    states = set()
    for ref, state in rules.items():
        sub = f"{label}.rules[{ref}]"
        if not isinstance(state, dict):
            raise _error(f"{sub} must be an object", "schema_violation")
        if set(state) - {"digest", "state", "verified_through", "findings"}:
            raise _error(f"{sub} has undeclared member(s): " + ",".join(sorted(set(state) - {"digest", "state", "verified_through", "findings"})),
                         "undeclared_member")
        for name in ("digest", "state", "verified_through", "findings"):
            if name not in state:
                raise _error(f"{sub}.{name} is required", "schema_violation")
        if state["digest"] is not None and not (isinstance(state["digest"], str) and DIGEST.match(state["digest"])):
            raise _error(f"{sub}.digest is not a sha256 digest", "schema_violation")
        _check_kind(state["state"], ("enum", _RULE_STATES), sub + ".state")
        _check_kind(state["verified_through"], ("enum", _VERIFIED), sub + ".verified_through")
        if not isinstance(state["findings"], list):
            raise _error(f"{sub}.findings must be an array", "schema_violation")
        for finding in state["findings"]:
            _check_kind(finding, ("enum", _FINDINGS), sub + ".findings")
        if state["state"] == "unknown":
            states.add(ref)
    if sorted(states) != sorted(unknown) or not all(isinstance(x, str) for x in unknown):
        raise _error(f"{label}.unknown differs from the rules whose state is unknown", "rule_identity_inconsistent")


def _binding_authority(decision: dict[str, Any]) -> dict[str, Any] | None:
    binding = decision.get("binding")
    return binding.get("runtime_authority") if isinstance(binding, dict) else None


def active_profiles(cp: dict[str, Any]) -> set[str]:
    """The profiles whose members the retained record shows (never inferred from anything but members)."""
    found: set[str] = set()
    decisions, attempts = _rows(cp, "decisions"), _rows(cp, "attempts")
    refusals, events = _rows(cp, "refusals"), _rows(cp, "check_events")
    if any(cp.get(f) for f in ("operations", "operation_renewals", "attempt_joins")) \
            or any(isinstance(_binding_authority(d), dict) and ({"operation_id", "operation_issuer"} & set(_binding_authority(d)))
                   for d in decisions if isinstance(d, dict)):
        found.add("operation-identity/0.1")
    if any(cp.get(f) for f in ("rule_revisions", "rule_revision_refusals")) \
            or any(isinstance(r, dict) and "rule_identity" in r for r in (*decisions, *refusals)):
        found.add("rule-revision/0.1")
    markers = ("deadline", "age_bound_seconds", "extension_id", "nonce")
    if any(cp.get(f) for f in ("age_extensions", "age_extension_refusals", "recovery_runs")) \
            or any(isinstance(r, dict) and "evaluated_at" in r for r in (*decisions, *attempts)) \
            or any(isinstance(e, dict) and (set(markers) & set(e) or e.get("phase") in ("overdue", "expired")) for e in events) \
            or any(isinstance(r, dict) and ("deadline" in r or "evaluated_at" in r) for r in refusals):
        found.add("freshness/0.1")
    if any(cp.get(f) for f in ("merge_records", "compensation_obligations")):
        found.add("merge-record/0.1")
    if cp.get("snapshot_uses"):
        found.add("reversibility/0.1")
    if cp.get("dedupe_escalations"):
        found.add("dedupe-ttl/0.1")
    return found


def freshness_on(cp: dict[str, Any]) -> bool:
    return "freshness/0.1" in active_profiles(cp)


def validate_rows(cp: dict[str, Any]) -> None:
    """Structure of every profile list and of the profile members inside rows (closed sets, enums, times, extensions)."""
    for field, spec in SPECS.items():
        for i, raw in enumerate(_rows(cp, field)):
            check_row(raw, f"{field}[{i}]", spec)
    for i, raw in enumerate(_rows(cp, "rule_revision_refusals")):
        check_row(raw["revision"], f"rule_revision_refusals[{i}].revision", _REVISION)
        if not raw["reasons"] or not all(isinstance(x, str) and x for x in raw["reasons"]):
            raise _error(f"rule_revision_refusals[{i}].reasons must be non-empty reasons", "schema_violation")
    for i, raw in enumerate(_rows(cp, "age_extension_refusals")):
        check_row(raw["extension"], f"age_extension_refusals[{i}].extension", {k: (v[0], v[1]) for k, v in _EXTENSION.items()})
        reasons = raw["reasons"]
        for reason in reasons:
            _check_kind(reason, ("enum", _EXTENSION_REFUSAL_REASONS), f"age_extension_refusals[{i}].reasons")
        if not reasons or reasons != sorted(set(reasons)):
            raise _error(f"age_extension_refusals[{i}].reasons are not canonical (sorted, unique, non-empty)",
                         "extension_refusal_reasons_not_canonical")
    for field in ("decisions", "refusals"):
        for i, row in enumerate(_rows(cp, field)):
            if "rule_identity" in row:
                _check_rule_identity(row["rule_identity"], f"{field}[{i}].rule_identity")
    for i, row in enumerate(_rows(cp, "decisions")):
        for name in ("evaluated_at", "recorded_at"):
            if name in row:
                instant(row[name], f"decisions[{i}].{name}")
        authority = _binding_authority(row)
        if isinstance(authority, dict):
            names = {"operation_id", "operation_issuer"} & set(authority)
            if names and names != {"operation_id", "operation_issuer"}:
                raise _error(f"decisions[{i}].binding.runtime_authority carries only one of operation_id/operation_issuer",
                             "schema_violation")
            for name in names:
                if not (isinstance(authority[name], str) and authority[name]):
                    raise _error(f"decisions[{i}].binding.runtime_authority.{name} must be a non-empty string", "schema_violation")
    for i, row in enumerate(_rows(cp, "attempts")):
        for name in ATTEMPT_PROFILE_MEMBERS:
            if name in row:
                instant(row[name], f"attempts[{i}].{name}")
    for i, row in enumerate(_rows(cp, "refusals")):
        if "check_id" in row and not (isinstance(row["check_id"], str) and row["check_id"]):
            raise _error(f"refusals[{i}].check_id must be a non-empty string", "schema_violation")
        for name in ("evaluated_at", "deadline"):
            if name in row:
                instant(row[name], f"refusals[{i}].{name}")
    for i, row in enumerate(_rows(cp, "resolution_checks")):
        if "recorded_at" in row:
            instant(row["recorded_at"], f"resolution_checks[{i}].recorded_at")
    for i, row in enumerate(_rows(cp, "check_events")):
        for name in ("deadline", "evaluated_at"):
            if name in row:
                instant(row[name], f"check_events[{i}].{name}")
        if "age_bound_seconds" in row and not (type(row["age_bound_seconds"]) is int and row["age_bound_seconds"] >= 0):
            raise _error(f"check_events[{i}].age_bound_seconds must be a non-negative integer", "schema_violation")
        for name in ("extension_id", "nonce"):
            if name in row and not (isinstance(row[name], str) and row[name]):
                raise _error(f"check_events[{i}].{name} must be a non-empty string", "schema_violation")


def _validate_identity(cp: dict[str, Any]) -> None:
    decisions, attempts, refusals = _rows(cp, "decisions"), _rows(cp, "attempts"), _rows(cp, "refusals")
    operations, renewals, joins = _rows(cp, "operations"), _rows(cp, "operation_renewals"), _rows(cp, "attempt_joins")
    events = _rows(cp, "check_events")
    _unique(operations, "operation_id", "duplicate_operation_id", "operation")
    _unique(renewals, "renewal_id", "duplicate_renewal_id", "renewal")
    _unique(joins, "join_id", "duplicate_join_id", "join")
    _unique(joins, "attempt_id", "duplicate_attempt_join", "attempt join")
    ledger = {o["operation_id"]: o for o in operations}
    by_decision = {d["decision_id"]: d for d in decisions}
    attempt_rows = {a["attempt_id"]: a for a in attempts}
    opening = {e["check_id"]: e for e in events if e.get("phase") == "opened"}
    completed = {e["check_id"] for e in events if e.get("phase") == "completed"}
    for d in decisions:
        binding = d.get("binding")
        if not isinstance(binding, dict):
            continue
        authority = binding.get("runtime_authority") or {}
        op = authority.get("operation_id")
        if op is None:
            raise _error(f"authorized decision {d['decision_id']} carries no operation_id while operation identity is on",
                         "decision_operation_id_missing")
        row = ledger.get(op)
        if row is None:
            raise _error(f"decision {d['decision_id']} names operation {op!r} that no ledger row admits", "decision_operation_unadmitted")
        if row["issuer"] != authority.get("operation_issuer"):
            raise _error(f"decision {d['decision_id']} operation issuer differs from the ledger", "operation_issuer_mismatch")
        if row["grant_id"] != binding.get("grant_id"):
            raise _error(f"decision {d['decision_id']} grant differs from its operation's grant", "decision_operation_binding_mismatch")
    for r in renewals:
        accepted = r["outcome"] == "accepted"
        if accepted != (r["refusal_code"] is None):
            raise _error(f"renewal {r['renewal_id']} outcome and refusal_code disagree", "renewal_outcome_inconsistent")
        if r["operation_id"] not in ledger and (accepted or r["refusal_code"] != "operation_not_admitted"):
            raise _error(f"renewal {r['renewal_id']} names an operation that no ledger row admits", "renewal_accepted_unadmitted_operation")
    for j in joins:
        if j["operation_id"] not in ledger:
            raise _error(f"join {j['join_id']} names an operation that no ledger row admits", "join_operation_not_admitted")
        a = attempt_rows.get(j["attempt_id"])
        if a is None:
            raise _error(f"join {j['join_id']} names an attempt that does not exist", "join_attempt_missing")
        if a["effect_id"] != j["effect_id"] or a["decision_id"] != j["decision_id"]:
            raise _error(f"join {j['join_id']} effect or decision differs from its attempt", "join_attempt_mismatch")
        d = by_decision.get(j["decision_id"])
        if d is None:
            raise _error(f"join {j['join_id']} names a decision that does not exist", "join_decision_missing")
        binding = d.get("binding")
        if not isinstance(binding, dict) or d.get("result") != "authorized":
            raise _error(f"join {j['join_id']} names a decision that is not authorized", "join_decision_unauthorized")
        if (binding.get("runtime_authority") or {}).get("operation_id") != j["operation_id"]:
            raise _error(f"join {j['join_id']} operation differs from its decision's", "join_operation_mismatch")
        if binding.get("grant_id") != j["grant_id"] or binding.get("grant_revision") != j["grant_revision"]:
            raise _error(f"join {j['join_id']} grant or revision differs from its decision's binding", "join_binding_mismatch")
        if d.get("effect_id") != j["effect_id"]:
            raise _error(f"join {j['join_id']} effect differs from its decision's", "join_effect_mismatch")
        if j["merged_into"] is not None:
            if j["merged_into"] == j["operation_id"]:
                raise _error(f"join {j['join_id']} is merged into its own operation", "merged_into_self")
            if j["merged_into"] not in ledger:
                raise _error(f"join {j['join_id']} is merged into an operation that no ledger row admits", "merged_into_not_admitted")
        event = opening.get(j["check_id"])
        if event is None or event.get("stage") != "effect":
            raise _error(f"join {j['join_id']} names no opened effect-stage check", "join_check_missing")
        if event.get("effect_id") != j["effect_id"] or event.get("decision_id") != j["decision_id"]:
            raise _error(f"join {j['join_id']} check names another effect or decision", "join_check_lineage")
        if j["check_id"] not in completed:
            raise _error(f"join {j['join_id']} check never completed", "join_check_not_completed")
    joined = {j["attempt_id"] for j in joins}
    for a in attempts:
        if a["attempt_id"] not in joined:
            raise _error(f"attempt {a['attempt_id']} has no join row while operation identity is on", "attempt_without_join")
    for r in refusals:
        if r.get("check_id") is None:
            raise _error(f"refusal {r.get('refusal_id')} carries no check_id while operation identity is on", "refusal_check_id_missing")


def _validate_refusal_checks(cp: dict[str, Any]) -> None:
    """A refusal that names its journal check (operation identity and freshness both write it) names an opened effect-stage
    check of the same effect and decision."""
    opening = {e["check_id"]: e for e in _rows(cp, "check_events") if e.get("phase") == "opened"}
    for r in _rows(cp, "refusals"):
        check = r.get("check_id")
        if check is None:
            continue
        event = opening.get(check)
        if event is None or event.get("stage") != "effect":
            raise _error(f"refusal {r['refusal_id']} names no opened effect-stage check", "refusal_check_missing")
        if event.get("effect_id") != r["effect_id"] or event.get("decision_id") != r["decision_id"]:
            raise _error(f"refusal {r['refusal_id']} check names another effect or decision", "refusal_check_lineage")


def _validate_rules(cp: dict[str, Any]) -> None:
    revisions, refusals_log = _rows(cp, "rule_revisions"), _rows(cp, "rule_revision_refusals")
    _unique(revisions, "revision_id", "duplicate_revision_id", "rule revision")
    _unique(refusals_log, "refusal_id", "duplicate_revision_refusal_id", "rule revision refusal")
    registry_digests = {c.get("registry_digest") for c in _rows(cp, "vocabulary_changes") if isinstance(c, dict)}
    for field in ("decisions", "refusals"):
        for row in _rows(cp, field):
            identity = row.get("rule_identity")
            if identity is None:
                continue
            at = row.get("evaluated_at") or row.get("decided_at") or row.get("recorded_at")
            for ref, state in identity["rules"].items():
                if state["state"] != "adopted":
                    continue
                backed = state["digest"] in registry_digests or any(
                    r["rule_ref"] == ref and r["to_digest"] == state["digest"]
                    and (at is None or instant(r["recorded_at"], "rule_revisions.recorded_at") <= instant(at, "row time"))
                    for r in revisions)
                if not backed:
                    raise _error(f"{field} row adopts rule {ref!r} at a digest no revision row (recorded by then) supports",
                                 "rule_identity_unbacked")


def _validate_freshness(cp: dict[str, Any]) -> None:
    decisions, attempts, refusals = _rows(cp, "decisions"), _rows(cp, "attempts"), _rows(cp, "refusals")
    checks, events = _rows(cp, "resolution_checks"), _rows(cp, "check_events")
    extensions, ext_refusals, runs = _rows(cp, "age_extensions"), _rows(cp, "age_extension_refusals"), _rows(cp, "recovery_runs")
    _unique(extensions, "extension_id", "duplicate_extension_id", "age extension")
    _unique(ext_refusals, "refusal_id", "duplicate_extension_refusal_id", "age extension refusal")
    _unique(runs, "run_id", "duplicate_recovery_run_id", "recovery run")
    for label, rows, alias in (("decision", decisions, "decided_at"), ("attempt", attempts, "started_at")):
        for row in rows:
            if ("evaluated_at" in row) != ("recorded_at" in row):
                raise _error(f"{label} row carries only one of evaluated_at/recorded_at", "profile_member_missing")
            if "evaluated_at" in row:
                if instant(row["recorded_at"], label) < instant(row["evaluated_at"], label):
                    raise _error(f"{label} row recorded before it was evaluated", "recorded_before_evaluated")
                if row.get(alias) is not None and instant(row[alias], alias) != instant(row["evaluated_at"], label):
                    raise _error(f"{label} {alias} differs from evaluated_at", "evaluation_alias_mismatch")
    for row in checks:
        if "recorded_at" in row and instant(row["recorded_at"], "resolution check") < instant(row["evaluated_at"], "resolution check"):
            raise _error("resolution check recorded before it was evaluated", "recorded_before_evaluated")
    ext_by_id = {e["extension_id"]: e for e in extensions}
    for e in extensions:
        if e["to_max_age_seconds"] <= e["from_max_age_seconds"] or instant(e["expires_at"], "extension") <= instant(e["not_before"], "extension"):
            raise _error(f"accepted extension {e['extension_id']} does not raise the bound over a non-empty window", "accepted_extension_invalid")
        if e["signer"] is None:
            raise _error(f"accepted extension {e['extension_id']} is unsigned", "accepted_extension_unsigned")
        if e["signer"] == e["requested_by"]:
            raise _error(f"accepted extension {e['extension_id']} is signed by its requester", "accepted_extension_self_signed")
    # Journal events, per check.
    by_check: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        by_check.setdefault(e["check_id"], []).append(e)
    expired_checks: dict[str, dict[str, Any]] = {}
    overdue_checks: set[str] = set()
    interrupted_checks: set[str] = set()
    for check_id, rows in by_check.items():
        first = rows[0]
        if first["phase"] != "opened":
            raise _error(f"check {check_id} has no opening as its first event", "check_opening_missing")
        if ("deadline" in first) != ("age_bound_seconds" in first):
            raise _error(f"check {check_id} opening carries only one of deadline/age_bound_seconds", "deadline_members_incomplete")
        if "deadline" in first:
            expect = instant(first["recorded_at"], "event") + timedelta(seconds=first["age_bound_seconds"])
            if instant(first["deadline"], "event") != expect:
                raise _error(f"check {check_id} deadline is not its opening plus age_bound_seconds", "deadline_mismatch")
        if "extension_id" in first:
            ext = ext_by_id.get(first["extension_id"])
            if ext is None:
                raise _error(f"check {check_id} names an extension that no age_extensions row records", "extension_unknown")
            if first.get("age_bound_seconds") != ext["to_max_age_seconds"]:
                raise _error(f"check {check_id} age bound differs from its extension's", "extension_bound_mismatch")
        previous = instant(first["recorded_at"], "event")
        for later in rows[1:]:
            if later["phase"] == "opened":
                raise _error(f"check {check_id} is opened twice", "duplicate_check_opening")
            for name in ("deadline", "age_bound_seconds", "extension_id", "nonce"):
                if later.get(name) != first.get(name):
                    raise _error(f"check {check_id} event changes {name} after the opening", "check_event_clock_drift")
            now = instant(later["recorded_at"], "event")
            if now < previous:
                raise _error(f"check {check_id} events move backwards in time", "check_event_time_regression")
            previous = now
        phases = [r["phase"] for r in rows]
        if phases.count("overdue") > 1:
            raise _error(f"check {check_id} is reported overdue more than once", "overdue_repeated")
        for r in rows:
            if r["phase"] in ("overdue", "expired"):
                if "deadline" not in first:
                    raise _error(f"check {check_id} has an {r['phase']} event but no deadline", f"{r['phase']}_without_deadline")
                if r["reasons"] != [OVERDUE if r["phase"] == "overdue" else EXPIRED]:
                    raise _error(f"check {check_id} {r['phase']} event carries other reasons", "phase_reasons_mismatch")
                if instant(r["recorded_at"], "event") <= instant(first["deadline"], "event"):
                    raise _error(f"check {check_id} {r['phase']} event is not after its deadline",
                                 f"{r['phase']}_not_past_deadline" if r["phase"] == "expired" else "overdue_before_deadline")
        if "overdue" in phases:
            overdue_checks.add(check_id)
        if "interrupted" in phases:
            interrupted_checks.add(check_id)
        if "expired" in phases:
            expired_checks[check_id] = first
    expired_refusals = {r["check_id"]: r for r in refusals if EXPIRED in (r.get("reasons") or [])}
    for r in refusals:
        if EXPIRED in (r.get("reasons") or []) and ("check_id" not in r or "deadline" not in r):
            raise _error(f"refusal {r['refusal_id']} for {EXPIRED} lacks check_id or deadline", "expired_refusal_mismatch")
    if set(expired_checks) != set(expired_refusals):
        raise _error("expired checks and refusals with check_expired_before_dispatch do not pair by check_id", "expired_refusal_mismatch")
    failed = {(a["effect_id"]) for a in attempts if a.get("status") == "failed" and a.get("error") == EXPIRED}
    for check_id, refusal in expired_refusals.items():
        if instant(refusal["deadline"], "refusal") != instant(expired_checks[check_id]["deadline"], "event"):
            raise _error(f"refusal {refusal['refusal_id']} deadline differs from its check's", "expired_refusal_deadline_mismatch")
        if refusal["effect_id"] not in failed:
            raise _error(f"refusal {refusal['refusal_id']} has no failed attempt carrying {EXPIRED}", "expired_without_failed_attempt")
    for a in attempts:
        if a.get("error") == EXPIRED and a.get("status") != "failed":
            raise _error(f"attempt {a['attempt_id']} carries {EXPIRED} but is not failed", "expired_attempt_not_failed")
    for run in runs:
        if (run["oldest_open_age_seconds"] is None) != (run["open_count"] == 0):
            raise _error(f"recovery run {run['run_id']} oldest age and open count disagree", "recovery_run_oldest_age_inconsistent")
        if run["open_count"] < len(run["overdue"]):
            raise _error(f"recovery run {run['run_id']} open count is below its overdue checks", "recovery_run_open_count_below_overdue")
        for ids, known, code in ((run["overdue"], overdue_checks, "recovery_overdue_without_event"),
                                 (run["interrupted"], interrupted_checks, "recovery_interrupted_without_event")):
            if not all(isinstance(x, str) for x in ids) or set(ids) - known:
                raise _error(f"recovery run {run['run_id']} names a check without the matching journal event", code)
    # A decision held for check_lease_unavailable has no other reason and was never dispatched.
    decided = {a["decision_id"] for a in attempts}
    for d in decisions:
        if "check_lease_unavailable" in (d.get("reasons") or []):
            if d["reasons"] != ["check_lease_unavailable"]:
                raise _error(f"decision {d['decision_id']} carries other reasons next to check_lease_unavailable", "lease_unavailable_with_other_reasons")
            if d["decision_id"] in decided:
                raise _error(f"decision {d['decision_id']} held for check_lease_unavailable was dispatched", "lease_unavailable_dispatched")
    # A mismatched nonce read is never nonce-bound.
    for row in [*events, *checks, *refusals, *decisions]:
        inputs = [row["input"]] if isinstance(row.get("input"), dict) else row.get("inputs") or row.get("resolution_inputs") or []
        for item in inputs:
            if isinstance(item, dict) and item.get("read_state") == "nonce_mismatch" and item.get("age_basis") == "nonce_bound":
                raise _error("an input with read_state nonce_mismatch is recorded as nonce_bound", "nonce_mismatch_basis")


def _validate_merges(cp: dict[str, Any]) -> None:
    merges, obligations, joins = _rows(cp, "merge_records"), _rows(cp, "compensation_obligations"), _rows(cp, "attempt_joins")
    _unique(merges, "merge_id", "duplicate_merge_id", "merge record")
    _unique(obligations, "obligation_id", "duplicate_obligation_id", "compensation obligation")
    ledger = {o["operation_id"] for o in _rows(cp, "operations")}
    effects = {a["effect_id"] for a in _rows(cp, "attempts")}
    by_id = {m["merge_id"]: m for m in merges}
    for m in merges:
        label = f"merge {m['merge_id']}"
        folded = m["folded_operation_ids"]
        if not folded or not all(isinstance(x, str) and x for x in folded) or len(set(folded)) != len(folded):
            raise _error(f"{label} folded_operation_ids must be distinct non-empty operation ids", "merge_operation_ids_invalid")
        if m["survivor_operation_id"] in folded:
            raise _error(f"{label} folds its own survivor", "merge_operation_ids_invalid")
        for finding in m["rule_findings"]:
            _check_kind(finding, ("enum", _FINDINGS), label + ".rule_findings")
        if instant(m["recorded_at"], label) < instant(m.get("evaluated_at", m["recorded_at"]), label):
            raise _error(f"{label} recorded before it was evaluated", "recorded_before_evaluated")
        if not all(isinstance(x, str) and x for x in m["reasons"]):
            raise _error(f"{label} reasons must be non-empty strings", "schema_violation")
        if (m["outcome"] == "merged") != (not m["reasons"]):
            raise _error(f"{label} outcome {m['outcome']!r} and its reasons disagree (only a merged record has none)", "merge_outcome_reasons_inconsistent")
        if m["outcome"] == "merged":
            if m["rule_state"] != "adopted":
                raise _error(f"{label} is merged under a rule that is not adopted", "merge_rule_not_adopted")
            if ledger and ({m["survivor_operation_id"], *folded} - ledger):
                raise _error(f"{label} merges an operation that no ledger row admits", "merge_operation_not_admitted")
        elif "compensation_obligation_id" in m:
            raise _error(f"{label} carries an obligation but its outcome is {m['outcome']!r}", "merge_obligation_without_merge")
    owned = {}
    for o in obligations:
        label = f"obligation {o['obligation_id']}"
        m = by_id.get(o["merge_id"])
        if m is None or m["outcome"] != "merged" or m.get("compensation_obligation_id") != o["obligation_id"]:
            raise _error(f"{label} names no merged merge record that names it back", "obligation_merge_mismatch")
        if o["survivor_operation_id"] != m["survivor_operation_id"] or set(o["operation_ids"]) != {m["survivor_operation_id"], *m["folded_operation_ids"]}:
            raise _error(f"{label} operations differ from its merge's", "obligation_merge_mismatch")
        owned[o["merge_id"]] = o
        per = o["effect_ids_by_operation"]
        listed = [e for v in per.values() if isinstance(v, list) for e in v]
        if set(per) - set(o["operation_ids"]) or not all(isinstance(v, list) for v in per.values()) or sorted(listed) != sorted(o["effect_ids"]):
            raise _error(f"{label} effect ids and their per-operation listing disagree", "obligation_effects_inconsistent")
        if set(o["effect_ids"]) - effects or set(o["unresolved_effect_ids"]) - effects:
            raise _error(f"{label} names an effect that no attempt row has", "obligation_effect_unknown")
        if len(o["effect_ids"]) < 2:
            raise _error(f"{label} lists fewer than two applied effects (a merge before the second effect leaves none)", "obligation_without_two_effects")
        if o["status"] != "recorded" or o["execution"] != "not_executed":
            raise _error(f"{label} claims execution (record only)", "obligation_executed")
    for m in merges:
        if m["outcome"] == "merged" and "compensation_obligation_id" in m and m["merge_id"] not in owned:
            raise _error(f"merge {m['merge_id']} names an obligation that no row records", "obligation_merge_mismatch")
    folded_of = {f for m in merges if m["outcome"] == "merged" for f in m["folded_operation_ids"]}
    for j in joins:
        if j["merged_into"] is not None and j["operation_id"] not in folded_of:
            raise _error(f"join {j['join_id']} is merged into another operation that no merged record folds", "merged_into_unrecorded")


def _validate_reversibility(cp: dict[str, Any]) -> None:
    uses = _rows(cp, "snapshot_uses")
    _unique(uses, "use_id", "duplicate_snapshot_use_id", "snapshot use")
    opened = {e["check_id"] for e in _rows(cp, "check_events") if e.get("phase") == "opened"}
    for u in uses:
        label = f"snapshot use {u['use_id']}"
        if not all(isinstance(x, str) and x for x in u["reasons"]):
            raise _error(f"{label} reasons must be non-empty strings", "schema_violation")
        if instant(u["recorded_at"], label) < instant(u["evaluated_at"], label):
            raise _error(f"{label} recorded before it was evaluated", "recorded_before_evaluated")
        if u["accepted"]:
            if u["basis"] != "cached_snapshot" or u["effective_status"] != "open" or u["reasons"]:
                raise _error(f"{label} is accepted but is not an open cached snapshot without reasons", "snapshot_use_inconsistent")
            if u["reversibility"] == "irreversible":
                raise _error(f"{label} accepts a cached snapshot for an irreversible class", "snapshot_use_irreversible_accepted")
            if u["age_seconds"] is None or u["snapshot_observed_at"] is None or u["age_seconds"] > u["age_bound_seconds"]:
                raise _error(f"{label} is accepted without an age inside its bound", "snapshot_use_age_inconsistent")
        elif u["effective_status"] != "closed" or not u["reasons"]:
            raise _error(f"{label} is refused but is not closed with reasons", "snapshot_use_inconsistent")
        if u.get("check_id") is not None and u["check_id"] not in opened:
            raise _error(f"{label} names no opened journal check", "snapshot_use_check_missing")


def _validate_dedupe(cp: dict[str, Any]) -> None:
    rows = _rows(cp, "dedupe_escalations")
    _unique(rows, "escalation_id", "duplicate_escalation_id", "dedupe escalation")
    _unique(rows, "effect_id", "duplicate_escalation_for_effect", "escalation for effect")
    effects = {a["effect_id"] for a in _rows(cp, "attempts")}
    for e in rows:
        label = f"escalation {e['escalation_id']}"
        if e["effect_id"] not in effects:
            raise _error(f"{label} names an effect that no attempt row has", "escalation_effect_unknown")
        first, horizon, deadline, expires, fired = (instant(e[k], label) for k in (
            "first_attempt_at", "provider_horizon_at", "escalation_deadline_at", "key_expires_at", "fired_at"))
        if not (first <= horizon <= deadline < expires):
            raise _error(f"{label} horizon, deadline and key expiry are not ordered first <= horizon <= deadline < expiry",
                         "escalation_not_inside_key_ttl")
        if fired < deadline:
            raise _error(f"{label} fired before its deadline", "escalation_before_deadline")
        inside = fired < expires
        if e["fired_inside_key_ttl"] != inside:
            raise _error(f"{label} fired_inside_key_ttl disagrees with its times", "escalation_flag_mismatch")
        if e["reasons"] != ["attempt_unresolved_past_horizon"] + ([] if inside else ["escalation_after_key_ttl"]):
            raise _error(f"{label} reasons disagree with its timing", "escalation_reasons_mismatch")
        safe = e["same_key_safe_until"]
        if (e["mode"] == "destination_ttl") != (safe is not None) or (safe is not None and instant(safe, label) != expires):
            raise _error(f"{label} same_key_safe_until disagrees with its mode", "escalation_same_key_mismatch")


def validate_cross_rows(cp: dict[str, Any]) -> set[str]:
    """Refuse a damaged profile-on record; returns the active profiles (empty set: nothing to check)."""
    profiles = active_profiles(cp)
    _validate_refusal_checks(cp)
    if "operation-identity/0.1" in profiles:
        _validate_identity(cp)
    if "rule-revision/0.1" in profiles:
        _validate_rules(cp)
    if "freshness/0.1" in profiles:
        _validate_freshness(cp)
    if "merge-record/0.1" in profiles:
        _validate_merges(cp)
    if "reversibility/0.1" in profiles:
        _validate_reversibility(cp)
    if "dedupe-ttl/0.1" in profiles:
        _validate_dedupe(cp)
    return profiles
