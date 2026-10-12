"""Optional, non-effecting inspection of a pinned synthetic recovery export.

This is not ReconstructionBundle 0.2.0 or a bounded-workflow importer.
Digests establish internal consistency of supplied bytes, never authenticity.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

RUNTIME_REVISION = "8e7d634cf0a22b6f3c1fc6d93afe92c7414fa243"
PROFILE = "cognous-recovery-resolution/synthetic-0.1"
EXPORT_FORMAT = "cognous-recovery-inspection/synthetic-0.1"
INSPECTION_FORMAT = "cognous-replay-recovery-inspection/0.1"
CANONICALIZATION = "python-json-sort-ascii-compact/1"
POLICY = "synthetic-structural/2"
IDENTITY = ("effect_id", "attempt_id", "decision_id", "grant_id", "grant_revision")
LIMITATIONS = ["synthetic_assertions_only", "not_a_replay_or_evidence_pack_mapping",
              "no_source_authentication", "no_settlement_verification",
              "legacy_facts_do_not_resolve_synthetic_work"]
LEGACY_GAPS = ["observer_ref", "watermark_ref", "provider_acceptance_ref",
               "evidence_location_ref", "observation_digest", "admission_policy"]
REASONS = {"event_id_reused_with_changed_body", "adapter_id_changed",
           "client_reference_changed", "ordering_domain_changed", "source_order_not_increasing",
           "known_effect_contradicted", "applied_regressed_to_partial",
           "finality_regressed", "coverage_regressed"}


class RecoveryInspectionError(ValueError):
    """Supplied inspection evidence violates the supported contract."""


def _require(ok, reason):
    if not ok:
        raise RecoveryInspectionError(reason)


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _equal(left, right, reason):
    _require(_json(left) == _json(right), reason)


def _digest(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _time(value):
    _require(isinstance(value, str), "timestamp must be text")
    stamp = datetime.fromisoformat(value)
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "timestamp requires timezone")
    return stamp.astimezone(timezone.utc)


def _observation(data, identity, event_id):
    strings = {"event_id", "effect_id", "attempt_id", "adapter_id", "client_reference",
               "state", "observed_at", "ordering_domain", "observation_ref",
               "observation_digest", "observer_ref", "watermark_ref",
               "provider_acceptance_ref", "evidence_location_ref"}
    _require(isinstance(data, dict) and set(data) == strings | {"order", "final", "complete_coverage"},
             "unsupported observation fields")
    _require(all(isinstance(data[k], str) and data[k].strip() for k in strings), "invalid observation text")
    _require(data["state"] in {"unknown", "absent", "partial", "applied"}, "invalid observation state")
    _require(type(data["order"]) is int and 0 <= data["order"] < 2**63, "invalid observation order")
    _require(type(data["final"]) is bool and type(data["complete_coverage"]) is bool, "invalid finality flags")
    _require(_sha(data["observation_digest"]), "invalid source digest")
    _equal(data["observed_at"], _time(data["observed_at"]).isoformat(), "noncanonical observation time")
    for key in ("effect_id", "attempt_id"):
        _equal(data[key], identity[key], "observation identity mismatch")
    _equal(data["event_id"], event_id, "event identity mismatch")


def _conflicts(previous, data):
    reasons = []
    if previous:
        for key in ("adapter_id", "client_reference", "ordering_domain"):
            if previous[key] != data[key]:
                reasons.append(f"{key}_changed")
        if data["order"] <= previous["order"]:
            reasons.append("source_order_not_increasing")
        if previous["state"] in {"applied", "partial"} and data["state"] in {"unknown", "absent"}:
            reasons.append("known_effect_contradicted")
        if previous["state"] == "applied" and data["state"] == "partial":
            reasons.append("applied_regressed_to_partial")
        if previous["final"] and not data["final"]:
            reasons.append("finality_regressed")
        if previous["complete_coverage"] and not data["complete_coverage"]:
            reasons.append("coverage_regressed")
    return reasons


def import_recovery_inspection(source, *, runtime_revision, expected_identity):
    """Validate supplied evidence and return a deterministic, loss-explicit copy.

    Caller must select the exact source revision and expected original identity.
    Neither caller assertions nor this validator authenticate that selection.
    No Runtime object, database, credentials, or effecting API is accessed.
    """
    try:
        # Only JSON-compatible values: reject coercible objects and nonfinite numbers.
        snapshot = json.loads(_json(source))
        return _import(snapshot, runtime_revision, expected_identity)
    except RecoveryInspectionError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise RecoveryInspectionError("malformed recovery inspection") from exc


def _import(source, runtime_revision, expected_identity):
    _require(runtime_revision == RUNTIME_REVISION, "unsupported Runtime revision")
    _require(isinstance(source, dict) and set(source) == {
        "export_format", "profile", "evaluated_at", "original", "disposition", "events",
        "current", "legacy", "limitations"}, "unsupported inspection fields")
    _require(source["profile"] == PROFILE and source["export_format"] == EXPORT_FORMAT,
             "unsupported recovery profile/export pair")
    _time(source["evaluated_at"])
    _equal(source["limitations"], LIMITATIONS, "missing or changed source limitations")
    _require(isinstance(source["original"], dict) and set(source["original"]) == set(IDENTITY) | {
        "state", "state_order", "ordering_ref", "completed_order", "completion_ref", "created_at"},
        "missing or unsupported original fields")
    _require(isinstance(source["disposition"], dict) and set(source["disposition"]) == {
        "effect_id", "attempt_id", "grant_id", "grant_revision", "status", "item_order", "revocation_order",
        "ordering_ref", "owner", "deadline", "reconciliation_ref", "created_at"},
        "missing or unsupported disposition fields")
    _require(isinstance(expected_identity, dict) and set(expected_identity) == set(IDENTITY),
             "explicit original identity required")
    _require(all(isinstance(expected_identity[k], str) and expected_identity[k].strip() for k in IDENTITY),
             "missing original identity")
    identity = {k: source["original"][k] for k in IDENTITY}
    _equal(identity, expected_identity, "original identity differs from selected identity")
    for key in ("effect_id", "attempt_id", "grant_id", "grant_revision"):
        _equal(source["disposition"][key], identity[key], "disposition identity mismatch")
    _require(source["disposition"]["status"] == "in_doubt", "original uncertainty is missing")
    current = {"profile": PROFILE, "revision": 0, "head_digest": None,
               "observation": "none", "finality": "unestablished", "work_state": "awaiting_observation",
               "retry_eligible": False, "execution_authority": "none", "settlement_verified": False}
    events = source["events"]
    _require(isinstance(events, list), "events must be an ordered array")
    checks, gaps, admitted_ids, seen_digests = [], [], set(), set()
    for revision, event in enumerate(events, 1):
        _require(isinstance(event, dict) and set(event) == {
            "revision", "event_id", "digest", "kind", "body", "admission"}, "unsupported event fields")
        _require(type(event["revision"]) is int and event["revision"] == revision, "noncontiguous revisions")
        _require(isinstance(event["event_id"], str) and event["event_id"].strip(), "missing event ID")
        _require(_sha(event["digest"]) and event["digest"] not in seen_digests, "invalid or duplicate envelope digest")
        seen_digests.add(event["digest"])
        receipt, body = event["admission"], event["body"]
        _require(isinstance(receipt, dict) and set(receipt) == {
            "profile", "policy", "assurance", "revision", "digest", "recorded_at", "kind", "identity",
            "prior_work_state", "conflict_reasons", "freshness_age_seconds", "checks", "reason"},
            "unsupported admission fields")
        for key, value in {"profile": PROFILE, "policy": POLICY, "assurance": "synthetic_admission",
                           "revision": revision, "digest": event["digest"], "kind": event["kind"],
                           "identity": identity, "prior_work_state": current["work_state"]}.items():
            _equal(receipt[key], value, "admission mismatch: " + key)
        _equal(receipt["checks"], {"structure": "passed", "retained_identity": "passed",
            "expected_revision": "passed", "predecessor": "passed", "freshness": "passed_synthetic_policy",
            "source_authentication": "not_established", "independent_verification": "not_established",
            "provider_finality": "not_established"}, "unsupported admission assurance")
        stamp = _time(receipt["recorded_at"])
        age = receipt["freshness_age_seconds"]
        _require(type(age) in (int, float) and 0 <= age <= 86400, "invalid recorded freshness")
        reasons = receipt["conflict_reasons"]
        _require(isinstance(reasons, list) and all(isinstance(x, str) and x in REASONS for x in reasons)
                 and len(reasons) == len(set(reasons)), "invalid conflict reasons")
        collision = event["event_id"] in admitted_ids
        if collision:
            _equal(body, {"conflicting_digest": event["digest"], "event_id": event["event_id"]},
                   "invalid collision commitment")
            _require(reasons and reasons[0] == "event_id_reused_with_changed_body", "collision reason missing")
            gaps.append({"path": f"events[{revision-1}].body", "state": "unavailable",
                         "reason": "producer_retained_commitment_only",
                         "checks_not_performed": ["submitted_body_digest", "submitted_predecessor", "observation_facts"]})
            digest_status = "not_performed_missing_preimage"
        else:
            _require(isinstance(body, dict) and set(body) == {"profile", "canonicalization", "observation",
                     "expected_revision", "predecessor_digest"}, "unsupported admission envelope")
            _equal(body["profile"], PROFILE, "mixed envelope profile")
            _equal(body["canonicalization"], CANONICALIZATION, "unsupported canonicalization")
            _equal(body["expected_revision"], revision-1, "envelope revision mismatch")
            _equal(body["predecessor_digest"], current["head_digest"], "broken predecessor")
            _require(_digest(body) == event["digest"], "submitted envelope digest mismatch")
            data = body["observation"]
            _observation(data, identity, event["event_id"])
            _require((stamp - _time(data["observed_at"])).total_seconds() == age, "freshness receipt mismatch")
            _equal(reasons, _conflicts(current.get("last_observation"), data), "conflict assessment mismatch")
            digest_status = "matched_supplied_canonical_bytes"
        held = current["work_state"] == "conflict_review"
        _equal(event["kind"], "disagreement" if reasons else "observation", "event kind mismatch")
        _equal(receipt["reason"], "conflict_hold" if reasons else
               ("existing_conflict_hold" if held else "synthetic_checks_passed"), "admission reason mismatch")
        if reasons or held:
            current.update(work_state="conflict_review", finality="unestablished")
        else:
            resolved = data["state"] == "applied" and data["complete_coverage"] and data["final"]
            current.update(observation=data["state"], last_observation=data,
                           finality="synthetic_profile_only" if resolved else "unestablished",
                           work_state="resolved" if resolved else
                           ("partial_followup" if data["state"] == "partial" else "awaiting_finality"))
        current.update(revision=revision, head_digest=event["digest"], identity=identity)
        admitted_ids.add(event["event_id"])
        checks.append({"revision": revision, "digest_check": digest_status})
    _equal(source["current"], current, "current projection does not match retained history")
    legacy = source["legacy"]
    if legacy is not None:
        _require(isinstance(legacy, dict) and set(legacy) == {
            "profile", "assurance", "record", "unavailable_provenance"}, "unsupported legacy fields")
        _equal(legacy["profile"], "cognous-revocation-closeout/1", "unsupported legacy profile")
        _equal(legacy["assurance"], "legacy_unverified", "unsupported legacy assurance")
        _equal(legacy["unavailable_provenance"], LEGACY_GAPS, "legacy provenance gap missing")
        _require(isinstance(legacy["record"], dict) and set(legacy["record"]) == {
            "attempt_id", "effect_id", "observation_state", "observation_order", "observation_ref",
            "closed", "retry_eligible", "reason", "created_at"}, "missing or unsupported legacy record fields")
        for key in ("effect_id", "attempt_id"):
            _equal(legacy["record"][key], identity[key], "legacy identity mismatch")
        gaps.extend({"path": "legacy.record." + key, "state": "unavailable",
                     "reason": "legacy_provenance_not_recorded"} for key in LEGACY_GAPS)
    return {"inspection_format": INSPECTION_FORMAT, "runtime_revision": runtime_revision,
            "expected_identity": deepcopy(expected_identity), "source": source,
            "source_content_sha256": _digest(source), "source_canonicalization": CANONICALIZATION,
            "event_checks": checks,
            "loss_report": {"dropped_fields": [], "unavailable_evidence": gaps,
                            "full_payload_reconstruction": "unavailable" if gaps else "retained_payloads_only"},
            "assurance": {"source_authentication": "not_established", "independent_verification": "not_established",
                          "settlement_verified": False, "execution_authority": "none", "retry_eligible": False,
                          "identity_check": "consistency_with_caller_selection_only",
                          "freshness_at_import": "not_evaluated"}}


def validate_recovery_inspection(inspection):
    """Revalidate a native inspection artifact, including every derived finding."""
    try:
        rebuilt = import_recovery_inspection(inspection["source"],
            runtime_revision=inspection["runtime_revision"], expected_identity=inspection["expected_identity"])
        _equal(inspection, rebuilt, "inspection mapping or loss/assurance report changed")
    except RecoveryInspectionError:
        raise
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise RecoveryInspectionError("malformed native recovery inspection") from exc
