"""Programme-2 generation 6093aca7: the N4 profiles (merge-record, reversibility, dedupe-ttl), the reason registry label 0.2, and
the executor pairing with the runtime 62a5cc15.

The valid cases are REAL run records and exports written by the Control Plane's and the runtime's own flows
(``tests/fixtures/programme2_profiles`` for the Control Plane record, ``tests/fixtures/programme2_paired`` for record plus executor
export; provenance in each ``PROVENANCE.json``). The acceptance, retention, rebuild and JSON round-trip of every Control Plane
fixture (N4 ones included) is run by ``test_programme2_profiles.py`` over the whole fixture directory; this file adds what is new:
the N4 refusals, the label rule, the earlier-generation behaviour and the pairing.

What this proves: acceptance and retention of the N4 members, closed member sets and cross-row couplings with stable codes, the two
registry labels, the exact runtime pairing. What it does not prove: that a profile was on, that any signer is authentic, that a
label matches the codes of its row (the verifier's work), or that the merge, reversibility or dedupe decisions re-derive.
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError, import_bounded_workflow
from agent_replay_bundle import importers as I
from agent_replay_bundle.programme2_profiles import PROFILE_LISTS

from .test_programme2_profiles import (FIX, P2, alter, do_import, first, load, mutate, refused, rebuild, run, shift)

PAIRED = Path(__file__).parent / "fixtures" / "programme2_paired"
N4_LISTS = {"merge_records": "merge_record", "compensation_obligations": "compensation_obligation",
            "snapshot_uses": "snapshot_use", "dedupe_escalations": "dedupe_escalation"}
LABEL_01, LABEL_02 = "runtime-authority-reasons/0.1", "runtime-authority-reasons/0.2"


# ------------------------------------------------------------------------------------------------ the generation tie
def test_generation_is_the_new_control_plane_revision_and_the_old_one_is_not_kept():
    assert I.CONTROL_PLANE_P2_REVISION == "6093aca7b945698e89c0d8ac7c75306375e1a298"
    assert I.BOUNDED_P2_PROFILE == "control-plane-programme2-profiles@6093aca7"
    assert I.MOLTBOT_P2_REVISION == "62a5cc156ecb439b4103b757fd265f276bb30374"
    assert I.MANIFEST_P2_REVISION == "f9ae8527326c07e3177b5f003e626b23758be3d0"
    for old in ("128eaa5e36fdff772fdc709581712dbeac046db3", "3755c71a20eab1a41135967b682342c809929572", "3cd17ead6b24301290ad1e50ae4b22bbd93c12fb"):  # the earlier ties are replaced
        assert old not in vars(I).values()
        with pytest.raises(ImportContractError, match="unsupported Control Plane revision"):
            import_bounded_workflow(run("default-path"), control_plane_revision=old)
    provenance = json.loads((FIX / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["producer"]["revision"] == P2


def test_every_n4_list_is_a_profile_list_and_appears_in_a_real_record():
    assert N4_LISTS.items() <= PROFILE_LISTS.items()
    for field in N4_LISTS:
        assert any(run(p.stem).get(field) for p in FIX.glob("*.json") if p.name != "PROVENANCE.json"), field


@pytest.mark.parametrize("name,field", [("merge-after-both-applied-obligation", "merge_records"),
                                        ("merge-after-both-applied-obligation", "compensation_obligations"),
                                        ("reversibility-cached-snapshot-accepted", "snapshot_uses"),
                                        ("dedupe-unknown-attempt-escalated", "dedupe_escalations")])
def test_n4_rows_are_retained_whole_as_their_record_type(name, field):
    bundle = do_import(run(name))
    kept = [r.data for r in bundle.records if r.record_type == N4_LISTS[field]]
    assert kept == run(name)[field]
    assert bundle.import_reports[0].field_mappings[field] == f"records[{N4_LISTS[field]}]"
    rebuilt, _ = rebuild(bundle)
    assert [r["data"] for r in rebuilt["records"] if r["record_type"] == N4_LISTS[field]] == run(name)[field]


def test_merged_into_on_a_join_is_retained_and_a_merge_that_never_dispatched_has_none():
    folded = do_import(run("merge-folded-operation-dispatches-under-survivor"))
    (join,) = [r.data for r in folded.records if r.record_type == "attempt_join"]
    assert join["merged_into"] == "op-order-100/refund-1" and join["operation_id"] == "op-order-100/refund-2"
    suppressed = do_import(run("merge-before-second-effect"))
    assert all(r.data["merged_into"] is None for r in suppressed.records if r.record_type == "attempt_join")


def test_a_refused_second_effect_after_a_merge_is_a_retained_refusal_with_the_new_label():
    bundle = do_import(run("merge-before-second-effect"))
    (refusal,) = [r.data for r in bundle.records if r.record_type == "effect_time_refusal"]
    assert refusal["reasons"] == ["operation_merged_effect_exists"] and refusal["reason_vocabulary_version"] == LABEL_02


def test_dedupe_in_progress_attempt_is_unknown_and_never_a_failure_here():
    bundle = do_import(run("dedupe-in-progress-blocks-new-key"))
    attempts = [r.data for r in bundle.records if r.record_type == "control_plane_attempt_transition"]
    assert any(a["status"] == "unknown" and a.get("error") == "destination_in_progress" for a in attempts)
    assert not [r for r in bundle.records if r.record_type == "dedupe_escalation"], "in progress alone writes no escalation row"


# ---------------------------------------------------------------------------------------------------- registry label
def _labelled(kind):
    for p in sorted(FIX.glob("*.json")):
        if p.name == "PROVENANCE.json":
            continue
        rows = run(p.stem).get(kind, [])
        if any(r.get("reason_vocabulary_version") == LABEL_02 for r in rows):
            return p.stem
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["refusals", "check_events"])
def test_label_02_rows_of_real_runs_are_accepted_and_retained_unchanged(kind):
    name = _labelled(kind)
    bundle = do_import(run(name))
    labels = {r.data["reason_vocabulary_version"] for r in bundle.records if r.record_type in ("effect_time_refusal", "resolution_check_event")}
    assert LABEL_02 in labels
    rebuilt, _ = rebuild(bundle)
    assert {r["data"]["reason_vocabulary_version"] for r in rebuilt["records"]
            if r["record_type"] in ("effect_time_refusal", "resolution_check_event")} == labels


def test_both_labels_are_accepted_on_a_decision_and_any_other_label_is_refused():
    base = "freshness-applied"
    for label in (LABEL_01, LABEL_02):
        cp = mutate(base, lambda cp: cp["decisions"][0].__setitem__("reason_vocabulary_version", label))
        assert do_import(cp).status
    refused(mutate(base, lambda cp: cp["decisions"][0].__setitem__("reason_vocabulary_version", "runtime-authority-reasons/0.3")), None)
    refused(mutate(base, lambda cp: cp["decisions"][0].pop("reason_vocabulary_version")), None)


@pytest.mark.parametrize("name,field", [("freshness-expired-before-dispatch", "refusals"), ("freshness-expired-before-dispatch", "check_events")])
def test_any_other_label_on_a_refusal_or_event_is_an_unknown_enum_value(name, field):
    def change(cp):
        row = first(cp[field], reason_vocabulary_version=LABEL_02)
        row["reason_vocabulary_version"] = "runtime-authority-reasons/0.3"
    refused(mutate(name, change), "unknown_enum_value")


def test_the_new_label_is_refused_by_every_earlier_generation_exactly_as_before():
    cp = run("freshness-expired-before-dispatch")
    with pytest.raises(ImportContractError):
        do_import(cp, I.CONTROL_PLANE_P4_REVISION)
    # the label is not what makes it refused there: the profile members are (earlier generations never accepted them)
    cp = run("rules-adopted-applied")
    assert LABEL_02 not in json.dumps(cp)
    bundle = do_import(cp, I.CONTROL_PLANE_P4_REVISION)
    assert any(f.code == "B001" for f in bundle.import_reports[0].findings)


@pytest.mark.parametrize("name", ["merge-after-both-applied-obligation", "reversibility-cached-snapshot-accepted", "dedupe-unknown-attempt-escalated"])
def test_earlier_generation_drops_the_n4_lists_as_unmapped_exactly_as_it_did_before(name):
    cp = run(name)
    try:
        bundle = do_import(cp, I.CONTROL_PLANE_P4_REVISION)
    except ImportContractError:
        return  # operation-identity members are refused there (undeclared_member), as the earlier tests pin
    assert not {r.record_type for r in bundle.records} & set(N4_LISTS.values())
    assert {f.path for f in bundle.import_reports[0].findings if f.code == "B001"} & set(N4_LISTS)


# ----------------------------------------------------------------------------------------------- damaged: N4 members
def drop(field, member):
    return lambda cp: cp[field][0].pop(member)


def put(field, member, value, **match):
    return alter(field, member, value, **match)


def dup(field, **changes):
    def change(cp):
        row = copy.deepcopy(cp[field][0])
        row.update(changes)
        cp[field].append(row)
    return change


MERGED, HELD, FOLDED, OBLIG = ("merge-after-both-applied-obligation", "merge-held-and-unknown-no-effect",
                               "merge-folded-operation-dispatches-under-survivor", "merge-after-both-applied-obligation")
SNAP_OK, SNAP_NO, SNAP_IRR = ("reversibility-cached-snapshot-accepted", "reversibility-cached-snapshot-stale-refused",
                              "reversibility-irreversible-class-refused")
DEDUPE = "dedupe-unknown-attempt-escalated"

N4_DAMAGE = [
    # merge records and obligations
    (MERGED, lambda cp: cp.pop("merge_records"), "obligation_merge_mismatch"),
    (MERGED, lambda cp: cp.pop("compensation_obligations"), "obligation_merge_mismatch"),
    (MERGED, drop("merge_records", "outcome"), "schema_violation"),
    (MERGED, drop("merge_records", "reason"), "schema_violation"),
    (MERGED, drop("merge_records", "folded_operation_ids"), "schema_violation"),
    (MERGED, drop("merge_records", "rule_state"), "schema_violation"),
    (MERGED, drop("compensation_obligations", "effect_ids"), "schema_violation"),
    (MERGED, drop("compensation_obligations", "execution"), "schema_violation"),
    (MERGED, put("merge_records", "reasons", ["merge_rule_unknown"]), "merge_outcome_reasons_inconsistent"),
    (MERGED, put("merge_records", "rule_state", "unknown"), "merge_rule_not_adopted"),
    (MERGED, put("merge_records", "folded_operation_ids", ["op-order-100/refund-1"]), "merge_operation_ids_invalid"),
    (MERGED, put("merge_records", "folded_operation_ids", []), "merge_operation_ids_invalid"),
    (MERGED, put("merge_records", "folded_operation_ids", ["op-never-admitted"]), "merge_operation_not_admitted"),
    (MERGED, put("merge_records", "rule_findings", ["made_up_finding"]), "unknown_enum_value"),
    (MERGED, put("merge_records", "outcome", "maybe"), "unknown_enum_value"),
    (MERGED, put("merge_records", "evaluated_at", "2027-01-01T00:00:00+00:00"), "recorded_before_evaluated"),
    (MERGED, put("merge_records", "recorded_at", "2026-10-05T19:00:00"), "timestamp_invalid"),
    (MERGED, dup("merge_records"), "duplicate_merge_id"),
    (MERGED, put("compensation_obligations", "status", "executed"), "unknown_enum_value"),
    (MERGED, put("compensation_obligations", "execution", "executed"), "unknown_enum_value"),
    (MERGED, put("compensation_obligations", "merge_id", "no-such-merge"), "obligation_merge_mismatch"),
    (MERGED, put("compensation_obligations", "survivor_operation_id", "op-other"), "obligation_merge_mismatch"),
    (MERGED, lambda cp: cp["compensation_obligations"][0]["effect_ids"].pop(), "obligation_effects_inconsistent"),
    (MERGED, lambda cp: cp["compensation_obligations"][0].update(effect_ids=["sha256:" + "0" * 64], effect_ids_by_operation={
        "op-order-100/refund-1": ["sha256:" + "0" * 64]}), "obligation_effect_unknown"),
    (MERGED, lambda cp: cp["compensation_obligations"][0].update(effect_ids=cp["compensation_obligations"][0]["effect_ids"][:1],
                                                                 effect_ids_by_operation={"op-order-100/refund-1": cp["compensation_obligations"][0]["effect_ids"][:1]}),
     "obligation_without_two_effects"),
    (MERGED, lambda cp: cp["merge_records"][0].pop("compensation_obligation_id"), "obligation_merge_mismatch"),
    (MERGED, dup("compensation_obligations"), "duplicate_obligation_id"),
    (HELD, lambda cp: cp["merge_records"][0].update(outcome="merged"), "merge_outcome_reasons_inconsistent"),
    (HELD, lambda cp: cp["merge_records"][0].update(compensation_obligation_id="x"), "merge_obligation_without_merge"),
    (HELD, lambda cp: cp["merge_records"][0].update(reasons=[]), "merge_outcome_reasons_inconsistent"),
    (FOLDED, lambda cp: cp["merge_records"][0].update(outcome="refused", reasons=["merge_operation_not_admitted"]), "merged_into_unrecorded"),
    (FOLDED, lambda cp: first(cp["attempt_joins"]).__setitem__("merged_into", first(cp["attempt_joins"])["operation_id"]), "merged_into_self"),
    # reversibility snapshot uses
    (SNAP_OK, put("snapshot_uses", "accepted", False), "snapshot_use_inconsistent"),
    (SNAP_OK, put("snapshot_uses", "reasons", ["purpose_cache_stale"]), "snapshot_use_inconsistent"),
    (SNAP_OK, put("snapshot_uses", "effective_status", "closed"), "snapshot_use_inconsistent"),
    (SNAP_OK, put("snapshot_uses", "age_seconds", 61), "snapshot_use_age_inconsistent"),
    (SNAP_OK, put("snapshot_uses", "age_seconds", None), "snapshot_use_age_inconsistent"),
    (SNAP_OK, put("snapshot_uses", "reversibility", "irreversible"), "snapshot_use_irreversible_accepted"),
    (SNAP_OK, put("snapshot_uses", "reversibility", "sometimes"), "unknown_enum_value"),
    (SNAP_OK, put("snapshot_uses", "basis", "guessed"), "unknown_enum_value"),
    (SNAP_OK, put("snapshot_uses", "age_basis", "nonce_bound"), "unknown_enum_value"),
    (SNAP_OK, put("snapshot_uses", "check_id", "no-such-check"), "snapshot_use_check_missing"),
    (SNAP_OK, put("snapshot_uses", "evaluated_at", "2027-01-01T00:00:00+00:00"), "recorded_before_evaluated"),
    (SNAP_OK, put("snapshot_uses", "age_bound_seconds", -1), "schema_violation"),
    (SNAP_OK, put("snapshot_uses", "accepted", "yes"), "schema_violation"),
    (SNAP_OK, drop("snapshot_uses", "age_basis"), "schema_violation"),
    (SNAP_OK, drop("snapshot_uses", "evaluated_at"), "schema_violation"),
    (SNAP_OK, drop("snapshot_uses", "accepted"), "schema_violation"),
    (SNAP_OK, dup("snapshot_uses"), "duplicate_snapshot_use_id"),
    (SNAP_NO, put("snapshot_uses", "accepted", True), "snapshot_use_inconsistent"),
    (SNAP_NO, put("snapshot_uses", "reasons", []), "snapshot_use_inconsistent"),
    (SNAP_IRR, lambda cp: cp["snapshot_uses"][0].update(accepted=True, reasons=[], effective_status="open"), "snapshot_use_irreversible_accepted"),
    # dedupe escalations
    (DEDUPE, drop("dedupe_escalations", "mode"), "schema_violation"),
    (DEDUPE, drop("dedupe_escalations", "fired_inside_key_ttl"), "schema_violation"),
    (DEDUPE, drop("dedupe_escalations", "key_expires_at"), "schema_violation"),
    (DEDUPE, put("dedupe_escalations", "mode", "forever"), "unknown_enum_value"),
    (DEDUPE, put("dedupe_escalations", "in_progress", "no"), "schema_violation"),
    (DEDUPE, put("dedupe_escalations", "fired_inside_key_ttl", False), "escalation_flag_mismatch"),
    (DEDUPE, put("dedupe_escalations", "reasons", ["attempt_unresolved_past_horizon", "escalation_after_key_ttl"]), "escalation_reasons_mismatch"),
    (DEDUPE, put("dedupe_escalations", "reasons", []), "escalation_reasons_mismatch"),
    (DEDUPE, put("dedupe_escalations", "effect_id", "sha256:" + "0" * 64), "escalation_effect_unknown"),
    (DEDUPE, put("dedupe_escalations", "same_key_safe_until", None), "escalation_same_key_mismatch"),
    (DEDUPE, put("dedupe_escalations", "mode", "none"), "escalation_same_key_mismatch"),
    (DEDUPE, lambda cp: cp["dedupe_escalations"][0].update(key_expires_at=cp["dedupe_escalations"][0]["escalation_deadline_at"],
                                                           same_key_safe_until=cp["dedupe_escalations"][0]["escalation_deadline_at"]),
     "escalation_not_inside_key_ttl"),
    (DEDUPE, lambda cp: cp["dedupe_escalations"][0].update(provider_horizon_at=shift(cp["dedupe_escalations"][0]["escalation_deadline_at"], 1)),
     "escalation_not_inside_key_ttl"),
    (DEDUPE, lambda cp: cp["dedupe_escalations"][0].update(fired_at=shift(cp["dedupe_escalations"][0]["escalation_deadline_at"], -1)),
     "escalation_before_deadline"),
    (DEDUPE, put("dedupe_escalations", "fired_at", "not a time"), "timestamp_invalid"),
    (DEDUPE, dup("dedupe_escalations"), "duplicate_escalation_id"),
    (DEDUPE, dup("dedupe_escalations", escalation_id="another-id"), "duplicate_escalation_for_effect"),
]


@pytest.mark.parametrize("name,change,code", N4_DAMAGE, ids=[f"{n}-{i}" for i, (n, _, _) in enumerate(N4_DAMAGE)])
def test_damaged_n4_record_is_refused_with_a_stable_code(name, change, code):
    refused(mutate(name, change), code)


def test_a_late_escalation_is_valid_when_its_flag_and_reason_say_so():
    def late(cp):
        e = cp["dedupe_escalations"][0]
        e["fired_at"] = e["recorded_at"] = shift(e["key_expires_at"], 5)
        e["fired_inside_key_ttl"] = False
        e["reasons"] = ["attempt_unresolved_past_horizon", "escalation_after_key_ttl"]
    assert do_import(mutate(DEDUPE, late)).status


UNKNOWN_N4 = [(n, f, f"{f}-{i}") for i, (n, f) in enumerate([
    (MERGED, "merge_records"), (MERGED, "compensation_obligations"), (SNAP_OK, "snapshot_uses"), (DEDUPE, "dedupe_escalations")])]


@pytest.mark.parametrize("name,field,_", UNKNOWN_N4, ids=[u[2] for u in UNKNOWN_N4])
def test_unknown_member_of_an_n4_row_is_refused_never_dropped(name, field, _):
    refused(mutate(name, lambda cp: cp[field][0].__setitem__("surprise", 1)), "undeclared_member")
    refused(mutate(name, lambda cp: cp[field][0].__setitem__("extensions", {"no-prefix": 1})), "invalid_extension_key")
    cp = mutate(name, lambda cp: cp[field][0].__setitem__("extensions", {"x-note": {"a": 1}}))
    kept = [r.data for r in do_import(cp).records if r.record_type == N4_LISTS[field]]
    assert kept[0]["extensions"] == {"x-note": {"a": 1}}


def test_unknown_top_level_list_next_to_the_n4_lists_is_still_reported_unmapped():
    cp = mutate(MERGED, lambda cp: cp.__setitem__("merge_records_extra", []))
    assert any(f.code == "B001" and f.path == "merge_records_extra" for f in do_import(cp).import_reports[0].findings)


def test_damage_after_export_to_an_n4_record_fails_revalidation_and_changes_the_digest():
    bundle = do_import(run(MERGED))
    dumped = bundle.model_dump(mode="json")
    record = next(r for r in dumped["records"] if r["record_type"] == "compensation_obligation")
    record["data"]["status"] = "executed"
    with pytest.raises(ImportContractError):
        rebuild_from(dumped)


def rebuild_from(dumped):
    from agent_replay_bundle.refusal_evidence import extend_retained_inputs
    by = lambda kind: [r["data"] for r in sorted(dumped["records"], key=lambda r: r["source_sequence"]) if r["record_type"] == kind]
    cp = {"run_id": dumped["run_id"], "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
          "observations": by("effect_observation"), "reconciliations": by("reconciliation")}
    return do_import(extend_retained_inputs(cp, dumped), dumped["metadata"]["control_plane_revision"])


# ------------------------------------------------------------------------------------------------ executor pairing
def paired(name):
    d = PAIRED / name
    return (json.loads((d / "control_plane_run.json").read_text()), json.loads((d / "proposal.json").read_text()),
            json.loads((d / "executor.json").read_text()))


SCENARIOS = ("adapter-default", "adapter-operation-identity", "atomic-default", "atomic-operation-key")


def pair_import(cp, proposal, export, revision=P2):
    return import_bounded_workflow(cp, proposal=proposal, moltbot_export=export, control_plane_revision=revision)


def test_paired_fixtures_are_unchanged_real_captures_of_the_pinned_pair():
    provenance = json.loads((PAIRED / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["producer"]["control_plane"] == I.CONTROL_PLANE_P2_REVISION
    assert provenance["producer"]["runtime"] == I.MOLTBOT_P2_REVISION
    assert set(provenance["sha256"]) == {f"{s}/{f}.json" for s in SCENARIOS for f in ("control_plane_run", "proposal", "executor")}
    for name, digest in provenance["sha256"].items():
        assert hashlib.sha256((PAIRED / name).read_bytes()).hexdigest() == digest, name
    assert hashlib.sha256((PAIRED / "capture_paired.py").read_bytes()).hexdigest() == provenance["script_sha256"]
    for s in SCENARIOS:
        assert paired(s)[2]["repository"]["revision"] == I.MOLTBOT_P2_REVISION


@pytest.mark.parametrize("name", SCENARIOS)
def test_real_executor_paired_run_imports_complete_with_the_runtime_profile(name):
    bundle = pair_import(*paired(name))
    assert bundle.status == "reconstruction_complete" and all(r.complete for r in bundle.import_reports)
    assert {p.profile_id for p in bundle.producer_profiles} == {I.BOUNDED_P2_PROFILE, I.MOLTBOT_P2_PROFILE}
    result = next(r for r in bundle.records if r.record_type == "execution_result")
    assert result.data["status"] == "executed"
    kinds = {r.record_type for r in bundle.records}
    assert {"destination_effect", "destination_attempt", "execution_envelope"} <= kinds


def test_identity_members_of_the_paired_adapter_run_are_retained():
    bundle = pair_import(*paired("adapter-operation-identity"))
    kinds = {r.record_type for r in bundle.records}
    assert {"operation", "attempt_join"} <= kinds
    assert not {"operation", "attempt_join"} & {r.record_type for r in pair_import(*paired("adapter-default")).records}


def test_the_atomic_route_record_has_no_attempt_rows_and_imports_anyway():
    cp, _, _ = paired("atomic-operation-key")
    assert cp["attempts"] == [] and "attempt_joins" not in cp, "the atomic route writes no attempt join (F-5 finding)"
    bundle = pair_import(*paired("atomic-operation-key"))
    assert bundle.status == "reconstruction_complete"


def test_the_operation_key_is_not_part_of_the_executor_export_and_the_export_is_the_default_shape():
    default, key = paired("atomic-default")[2], paired("atomic-operation-key")[2]
    assert set(default) == set(key)
    assert "operation_id" not in json.dumps(key) and "operation_effects" not in json.dumps(key)


@pytest.mark.parametrize("name", SCENARIOS)
def test_paired_export_is_refused_with_any_other_control_plane_revision(name):
    cp, proposal, export = paired(name)
    for revision in (I.CONTROL_PLANE_P4_REVISION, I.CONTROL_PLANE_F5B_REVISION):
        with pytest.raises(ImportContractError, match="unsupported executor/Control Plane revision combination"):
            pair_import(cp, proposal, export, revision)


def test_an_earlier_runtime_revision_is_still_not_paired_with_this_generation():
    cp, proposal, export = paired("adapter-default")
    for revision in (I.MOLTBOT_P4_REVISION, I.MOLTBOT_F5B_REVISION):
        other = copy.deepcopy(export)
        other["repository"]["revision"] = revision
        other["provenance"]["source_asserted"]["repository_revision"] = revision
        with pytest.raises(ImportContractError, match="unsupported executor/Control Plane revision combination"):
            pair_import(cp, proposal, other)


def test_the_new_runtime_revision_is_not_paired_with_any_earlier_control_plane():
    cp, proposal, export = paired("adapter-default")
    with pytest.raises(ImportContractError, match="unsupported executor/Control Plane revision combination"):
        pair_import(cp, proposal, export, I.CONTROL_PLANE_P4_REVISION)


@pytest.mark.parametrize("old", ["fc034d140ce55d9887ac3a0aab598f3a2c05ea47", "7170da59e04854a3dbe13f151400d0ac368b8dcb", "11de097c450d3ad4d89f9add41b00e38e7cc2c7c"])
def test_the_previous_runtime_pairings_are_replaced_not_kept(old):
    """The exact pairing moved from fc034d14 to 7170da59 to 11de097c to 62a5cc15 (the export shape is unchanged, the constant and captures moved)."""
    assert I.MOLTBOT_P2_REVISION != old and old not in vars(I).values()
    cp, proposal, export = paired("adapter-default")
    other = copy.deepcopy(export)
    other["repository"]["revision"] = old
    other["provenance"]["source_asserted"]["repository_revision"] = old
    with pytest.raises(ImportContractError, match="unsupported Moltbot producer repository revision"):
        pair_import(cp, proposal, other)


def test_an_unknown_runtime_revision_is_refused():
    cp, proposal, export = paired("adapter-default")
    other = copy.deepcopy(export)
    other["repository"]["revision"] = "0" * 40
    other["provenance"]["source_asserted"]["repository_revision"] = "0" * 40
    with pytest.raises(ImportContractError, match="unsupported Moltbot producer repository revision"):
        pair_import(cp, proposal, other)


def test_provenance_that_contradicts_the_repository_revision_is_refused():
    cp, proposal, export = paired("adapter-default")
    other = copy.deepcopy(export)
    other["provenance"]["source_asserted"]["repository_revision"] = I.MOLTBOT_P4_REVISION
    with pytest.raises(ImportContractError, match="provenance repository revision contradicts"):
        pair_import(cp, proposal, other)


def test_the_new_executor_profile_fails_closed_on_a_dangling_attempt_reference_like_every_2_0_profile():
    assert I.MOLTBOT_P2_PROFILE in I.STRICT_ACK_PROFILES


@pytest.mark.parametrize("name", ["adapter-operation-identity"])
def test_paired_damage_to_the_control_plane_side_is_still_refused(name):
    cp, proposal, export = paired(name)
    cp = copy.deepcopy(cp)
    cp["attempt_joins"].clear()
    with pytest.raises(ImportContractError) as info:
        pair_import(cp, proposal, export)
    assert info.value.code == "attempt_without_join"


def test_paired_export_damage_is_still_refused():
    cp, proposal, export = paired("adapter-default")
    other = copy.deepcopy(export)
    other["execution_result"]["status"] = "reconciled"
    with pytest.raises(ImportContractError):
        pair_import(cp, proposal, other)
