"""Programme-2 opt-in profiles: Replay accepts and retains the members of operation identity (N1), rule revision (N2) and
freshness (N3), and (since the 3755c71a re-capture) merge-record, reversibility and dedupe-ttl (N4, see
test_programme2_n4_and_pairing.py) for the exact Control Plane revision 3755c71a, refuses damaged ones with stable codes, and changes nothing with
the profiles off.

The valid cases are REAL run records written by the Control Plane's own flows (``tests/fixtures/programme2_profiles``, provenance
in ``PROVENANCE.json``, capture script in ``provenance/``). The invalid cases are single-defect mutations of those records.

What this proves: Replay's acceptance, retention through export and re-validation (the rebuild the Evidence Pack performs), and
its refusals. What it does not prove: that a profile was on (a record stripped of every profile member is a profile-off record),
that any signer is authentic, or that the producer's decisions re-derive (that is the verifier's work).
"""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from agent_replay_bundle import ImportContractError, import_bounded_workflow
from agent_replay_bundle.importers import (
    CONTROL_PLANE_P2_REVISION,
    CONTROL_PLANE_P4_REVISION,
    BOUNDED_P2_PROFILE,
)
from agent_replay_bundle.programme2_profiles import PROFILE_LISTS
from agent_replay_bundle.refusal_evidence import extend_retained_inputs

FIX = Path(__file__).parent / "fixtures" / "programme2_profiles"
P2 = CONTROL_PLANE_P2_REVISION
SCENARIOS = sorted(p.stem for p in FIX.glob("*.json") if p.name != "PROVENANCE.json")

OP, RULES, FRESH = "operation-identity/0.1", "rule-revision/0.1", "freshness/0.1"
MERGE, REVERSIBLE, DEDUPE = "merge-record/0.1", "reversibility/0.1", "dedupe-ttl/0.1"


def load(name):
    document = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    return document["run"], document["profiles"]


def run(name):
    return load(name)[0]


def do_import(cp, revision=P2):
    return import_bounded_workflow(cp, control_plane_revision=revision)


def refused(cp, code, revision=P2):
    with pytest.raises(ImportContractError) as info:
        do_import(cp, revision)
    assert info.value.code == code, (info.value.code, str(info.value))
    return info.value


def rebuild(bundle):
    """What the Evidence Pack does to re-validate a retained bundle: rebuild the Control Plane record from the retained
    records (``extend_retained_inputs``) and import it again."""
    dumped = bundle.model_dump(mode="json")
    by = lambda kind: [r["data"] for r in sorted(dumped["records"], key=lambda r: r["source_sequence"]) if r["record_type"] == kind]
    cp = {"run_id": dumped["run_id"], "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
          "observations": by("effect_observation"), "reconciliations": by("reconciliation")}
    cp = extend_retained_inputs(cp, dumped)
    return do_import(cp, dumped["metadata"]["control_plane_revision"]).model_dump(mode="json"), dumped


# ----------------------------------------------------------------------------------------------------- provenance
def test_fixtures_are_unchanged_real_captures():
    provenance = json.loads((FIX / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert provenance["producer"]["revision"] == P2
    assert set(provenance["sha256"]) == {f"{s}.json" for s in SCENARIOS}
    for name, digest in provenance["sha256"].items():
        assert hashlib.sha256((FIX / name).read_bytes()).hexdigest() == digest, name
    assert (FIX / "provenance" / "capture_programme2.py").is_file()


def test_profiles_the_fixtures_cover():
    covered = {p for s in SCENARIOS for p in load(s)[1]}
    assert covered == {OP, RULES, FRESH, MERGE, REVERSIBLE, DEDUPE}
    assert any(set(load(s)[1]) == {OP, RULES, FRESH} for s in SCENARIOS), "a run with all three profiles on is captured"
    members = {f for s in SCENARIOS for f in PROFILE_LISTS if run(s).get(f)}
    assert members == set(PROFILE_LISTS), "every profile list appears in at least one real record"


# ---------------------------------------------------------------------------------------------------- acceptance
@pytest.mark.parametrize("name", SCENARIOS)
def test_real_profile_run_is_accepted_and_every_profile_member_is_retained(name):
    cp = run(name)
    bundle = do_import(cp)
    assert bundle.metadata["control_plane_revision"] == P2
    assert bundle.producer_profiles[0].profile_id == BOUNDED_P2_PROFILE
    for field, kind in PROFILE_LISTS.items():
        retained = [r.data for r in bundle.records if r.record_type == kind]
        assert retained == cp.get(field, []), (name, field)
        paths = [r.source_path for r in bundle.records if r.record_type == kind]
        assert paths == [f"{field}[{i}]" for i in range(len(cp.get(field, [])))]
        assert (field in bundle.import_reports[0].field_mappings) == bool(cp.get(field))
    # members inside rows Replay already retained are kept verbatim (not dropped, not normalised)
    for kind, field in (("runtime_decision", "decisions"), ("control_plane_attempt_transition", "attempts"),
                        ("effect_time_refusal", "refusals"), ("resolution_check", "resolution_checks"),
                        ("resolution_check_event", "check_events")):
        assert [r.data for r in bundle.records if r.record_type == kind] == cp.get(field, [])
    assert not [f for f in bundle.import_reports[0].findings if f.code == "B001"], "no profile member is reported unmapped"


@pytest.mark.parametrize("name", SCENARIOS)
def test_retained_bundle_revalidates_to_the_same_bundle(name):
    bundle = do_import(run(name))
    again, dumped = rebuild(bundle)
    for field in ("records", "links", "commitments", "producer_profiles", "status", "import_reports", "semantics"):
        assert again[field] == dumped[field], (name, field)
    assert again["metadata"] == dumped["metadata"]


@pytest.mark.parametrize("name", SCENARIOS)
def test_the_export_survives_json_round_trip(name):
    from agent_replay_bundle import ReconstructionBundle
    bundle = do_import(run(name))
    restored = ReconstructionBundle.model_validate(json.loads(bundle.model_dump_json()))
    assert restored.records == bundle.records


def test_pack_inputs_are_the_record_types_the_freshness_block_reads():
    """The Evidence Pack's opt-in freshness block reads ``resolution_check_event``, ``recovery_run`` and ``effect_time_refusal``
    from the retained records; this pins the names and the members it counts on."""
    bundle = do_import(run("all-three-expired-before-dispatch"))
    events = [r.data for r in bundle.records if r.record_type == "resolution_check_event"]
    assert {"overdue", "expired"} & {e["phase"] for e in events}
    assert any("deadline" in e for e in events)
    refusals = [r.data for r in bundle.records if r.record_type == "effect_time_refusal"]
    assert any("check_expired_before_dispatch" in r["reasons"] and "deadline" in r for r in refusals)
    runs = [r.data for r in do_import(run("freshness-overdue-recovery-run")).records if r.record_type == "recovery_run"]
    assert runs and {"run_id", "trigger", "open_count", "overdue"} <= set(runs[0])


def test_live_overdue_and_abandoned_checks_are_retained_as_unfinished_evidence():
    """A check that is still open past its deadline, or that the reaper closed as abandoned, is retained with its journal events
    and recovery runs; the import says the authority evaluation did not complete (B006) and the bundle is partial."""
    live = do_import(run("freshness-live-overdue-check"))
    assert live.status == "reconstruction_partial"
    assert any(f.code == "B006" for f in live.import_reports[0].findings)
    events = [r.data for r in live.records if r.record_type == "resolution_check_event"]
    assert [e["phase"] for e in events].count("overdue") == 1
    opened = {e["check_id"] for e in events if e["phase"] == "opened"}
    closed = {e["check_id"] for e in events if e["phase"] in {"completed", "interrupted", "expired"}}
    assert len(opened - closed) == 1, "exactly the blocked check is open"
    abandoned = do_import(run("freshness-reaper-after-decision"))
    assert any(e.data["phase"] == "interrupted" for e in abandoned.records if e.record_type == "resolution_check_event")
    assert len([r for r in abandoned.records if r.record_type == "recovery_run"]) == 2


def test_expired_before_dispatch_is_a_retained_refusal_not_an_effect():
    bundle = do_import(run("freshness-expired-before-dispatch"))
    attempts = [r.data for r in bundle.records if r.record_type == "control_plane_attempt_transition"]
    assert [a["status"] for a in attempts] == ["attempted", "failed"] and attempts[-1]["error"] == "check_expired_before_dispatch"
    assert not [r for r in bundle.records if r.record_type == "effect_observation" and r.data["state"] in {"applied", "partial"}]


def test_observation_stamped_after_the_evaluation_pass_is_judged_against_the_recorded_service_clock():
    """freshness/0.1 judges 'future' against the service clock at reconciliation, not the evaluation pass: a destination stamp
    after the pass is accepted when the reconciliation was recorded at or after it, and refused when the recorded clock does
    not reach it (the profile-off rule, evaluation time as reference, is unchanged)."""
    cp = run("freshness-expired-observation-after-pass")
    do_import(cp)
    early = copy.deepcopy(cp)
    for rec in early["reconciliations"]:
        rec["reconciled_at"] = rec["evaluation_time"]
    with pytest.raises(ImportContractError, match="recorded temporal policy"):
        do_import(early)


# ------------------------------------------------------------------------------------------------ profiles off
def test_profile_off_run_of_the_new_revision_imports_like_the_previous_generation():
    """With every profile off the programme-2 generation adds nothing: same records, links, commitments and findings as the
    previous generation (only the revision and profile identifiers differ)."""
    cp = run("default-path")
    new, old = do_import(cp, P2).model_dump(mode="json"), do_import(cp, CONTROL_PLANE_P4_REVISION).model_dump(mode="json")

    def normal(bundle):
        text = json.dumps({f: bundle[f] for f in ("records", "links", "commitments", "import_reports", "status", "semantics")},
                          sort_keys=True)
        return (text.replace(BOUNDED_P2_PROFILE, "PROFILE").replace("control-plane-security-runtime@26a7e659", "PROFILE")
                .replace(P2, "REVISION").replace(CONTROL_PLANE_P4_REVISION, "REVISION"))
    assert normal(new) == normal(old)
    assert not {r.record_type for r in do_import(cp).records} & set(PROFILE_LISTS.values())


def test_earlier_generations_refuse_profile_members_exactly_as_before():
    """The members are accepted for the programme-2 revision only: every earlier generation keeps its behaviour."""
    refused(run("freshness-applied"), "undeclared_member", CONTROL_PLANE_P4_REVISION)
    refused(run("identity-applied-renewed"), "undeclared_member", CONTROL_PLANE_P4_REVISION)
    bundle = do_import(run("rules-adopted-applied"), CONTROL_PLANE_P4_REVISION)  # list dropped to B001, as before
    assert not {r.record_type for r in bundle.records} & set(PROFILE_LISTS.values())
    assert any(f.code == "B001" and f.path == "rule_revisions" for f in bundle.import_reports[0].findings)


def test_executor_export_is_not_paired_with_the_programme_2_revision():
    cp = run("default-path")
    export = {"execution_envelope": {"version": "0.2.0"}, "execution_result": {}, "effects": [], "attempts": [], "attempt_events": [],
              "producer_profile": {"profile_id": "urn:cognous:profiles:moltbot-safe-executor-producer", "profile_version": "2.0.0",
                                   "execution_envelope_version": "0.2.0"},
              "repository": {"repository": "cogno-us/moltbot-safe", "revision": "3024ef6e6ecf7da22e5f4fdf90d873f93b2a55c9",
                             "revision_status": "source_asserted"},
              "provenance": {"source_asserted": {"producer_profile_id": "urn:cognous:profiles:moltbot-safe-executor-producer",
                                                 "producer_profile_version": "2.0.0",
                                                 "repository_revision": "3024ef6e6ecf7da22e5f4fdf90d873f93b2a55c9"},
                             "independently_established": []}}
    with pytest.raises(ImportContractError, match="unsupported executor/Control Plane revision combination"):
        import_bounded_workflow(cp, moltbot_export=export, control_plane_revision=P2)


# ------------------------------------------------------------------------------------------- damaged: member dropped
def first(rows, **match):
    return next(r for r in rows if all(r.get(k) == v for k, v in match.items()))


def mutate(name, change):
    cp = copy.deepcopy(run(name))
    change(cp)
    return cp


def drop_list(field):
    return lambda cp: cp.pop(field)


def drop_member(field, member, **match):
    return lambda cp: first(cp[field], **match).pop(member)


def drop_binding_member(member):
    return lambda cp: first(cp["decisions"], result="authorized")["binding"]["runtime_authority"].pop(member)


DROPPED = [
    # operation identity
    ("identity-applied-renewed", drop_list("operations"), "decision_operation_unadmitted"),
    ("identity-applied-renewed", drop_list("attempt_joins"), "attempt_without_join"),
    ("identity-applied-renewed", drop_binding_member("operation_issuer"), "schema_violation"),
    ("identity-applied-renewed", drop_binding_member("operation_id"), "schema_violation"),
    ("identity-applied-renewed", lambda cp: cp["operations"][0].pop("issuer"), "schema_violation"),
    ("identity-applied-renewed", lambda cp: cp["attempt_joins"][0].pop("check_id"), "schema_violation"),
    ("identity-lost-ack-reconciled", lambda cp: cp["attempt_joins"].pop(), "attempt_without_join"),
    ("identity-effect-time-refusal", lambda cp: cp["refusals"][0].pop("check_id"), "refusal_check_id_missing"),
    # rule revision
    ("rules-adopted-applied", drop_list("rule_revisions"), "rule_identity_unbacked"),
    ("rules-adopted-applied", lambda cp: cp["decisions"][0]["rule_identity"].pop("unknown"), "schema_violation"),
    ("rules-self-signed-revision-refused", lambda cp: cp["rule_revision_refusals"][0].pop("reasons"), "schema_violation"),
    # freshness
    ("freshness-expired-before-dispatch", drop_member("check_events", "age_bound_seconds", phase="opened", stage="effect"),
     "deadline_members_incomplete"),
    ("freshness-expired-before-dispatch", lambda cp: cp["refusals"].clear(), "expired_refusal_mismatch"),
    ("freshness-expired-before-dispatch", lambda cp: cp["refusals"][0].pop("deadline"), "expired_refusal_mismatch"),
    ("freshness-expired-before-dispatch", lambda cp: cp["attempts"].pop(), "expired_without_failed_attempt"),
    ("freshness-applied", lambda cp: cp["decisions"][0].pop("recorded_at"), "profile_member_missing"),
    ("freshness-applied", lambda cp: cp["attempts"][1].pop("evaluated_at"), "profile_member_missing"),
    ("freshness-extension-accepted-and-refused", drop_list("age_extensions"), "extension_unknown"),
    ("freshness-extension-accepted-and-refused", lambda cp: cp["age_extension_refusals"][0].pop("recorded_at"), "schema_violation"),
    ("freshness-overdue-recovery-run", lambda cp: cp["recovery_runs"][0].pop("trigger"), "schema_violation"),
    ("freshness-overdue-recovery-run", lambda cp: [e for e in cp["check_events"] if e["phase"] == "overdue"] and None
     or cp["check_events"].__setitem__(slice(None), [e for e in cp["check_events"] if e["phase"] != "overdue"]),
     "recovery_overdue_without_event"),
    # combined
    ("all-three-expired-before-dispatch", drop_list("attempt_joins"), "attempt_without_join"),
    ("all-three-expired-before-dispatch", drop_list("rule_revisions"), "rule_identity_unbacked"),
    ("all-three-expired-before-dispatch", lambda cp: cp["refusals"].clear(), "expired_refusal_mismatch"),
]


@pytest.mark.parametrize("name,change,code", DROPPED, ids=[f"{n}-{i}" for i, (n, _, _) in enumerate(DROPPED)])
def test_dropped_profile_member_is_refused_with_a_stable_code(name, change, code):
    refused(mutate(name, change), code)


# ------------------------------------------------------------------------------------------ damaged: member altered
def alter(field, member, value, **match):
    def change(cp):
        first(cp[field], **match)[member] = value
    return change


def shift(stamp, seconds):
    from datetime import datetime, timedelta
    return (datetime.fromisoformat(stamp) + timedelta(seconds=seconds)).isoformat()


def rebound(cp, check_id, seconds):
    """Change a check's age bound coherently (bound and deadline on every event), so only the rule under test can fail."""
    rows = [e for e in cp["check_events"] if e["check_id"] == check_id]
    deadline = shift(rows[0]["recorded_at"], seconds)
    for e in rows:
        e["age_bound_seconds"], e["deadline"] = seconds, deadline


ALTERED = [
    ("identity-applied-renewed", lambda cp: first(cp["decisions"], result="authorized")["binding"]["runtime_authority"].update(
        operation_id="op-other"), "decision_operation_unadmitted"),
    ("identity-applied-renewed", lambda cp: first(cp["decisions"], result="authorized")["binding"]["runtime_authority"].update(
        operation_issuer="urn:cognous:principal:someone-else"), "operation_issuer_mismatch"),
    ("identity-applied-renewed", alter("attempt_joins", "effect_id", "sha256:" + "0" * 64), "join_attempt_mismatch"),
    ("identity-applied-renewed", alter("attempt_joins", "grant_revision", "9"), "join_binding_mismatch"),
    ("identity-applied-renewed", alter("attempt_joins", "operation_id", "op-other"), "join_operation_not_admitted"),
    ("identity-applied-renewed", alter("attempt_joins", "check_id", "no-such-check"), "join_check_missing"),
    ("identity-applied-renewed", alter("attempt_joins", "merged_into", "op-unknown"), "merged_into_not_admitted"),
    ("identity-applied-renewed", lambda cp: cp["attempt_joins"].append(copy.deepcopy(cp["attempt_joins"][0])), "duplicate_join_id"),
    ("identity-applied-renewed", lambda cp: cp["operations"].append(copy.deepcopy(cp["operations"][0])), "duplicate_operation_id"),
    ("identity-applied-renewed", alter("operation_renewals", "refusal_code", "renewal_revision_not_new", outcome="accepted"),
     "renewal_outcome_inconsistent"),
    ("identity-applied-renewed", alter("operations", "grant_id", "urn:cognous:grant:other"), "decision_operation_binding_mismatch"),
    ("identity-effect-time-refusal", alter("refusals", "check_id", "no-such-check"), "refusal_check_missing"),
    ("rules-adopted-applied", lambda cp: [v.update(digest="sha256:" + "1" * 64) for v in cp["decisions"][0]["rule_identity"]["rules"].values()],
     "rule_identity_unbacked"),
    ("rules-adopted-applied", lambda cp: [v.update(state="unknown") for v in cp["decisions"][0]["rule_identity"]["rules"].values()],
     "rule_identity_inconsistent"),
    ("rules-adopted-applied", lambda cp: [v.update(verified_through="trust-me") for v in cp["decisions"][0]["rule_identity"]["rules"].values()],
     "unknown_enum_value"),
    ("rules-adopted-applied", alter("rule_revisions", "recorded_at", "2026-10-06T00:00:00+00:00"), "rule_identity_unbacked"),
    ("rules-adopted-applied", alter("rule_revisions", "rule_kind", "policy-ish"), "unknown_enum_value"),
    ("freshness-expired-before-dispatch", lambda cp: [e.update(deadline=shift(e["deadline"], 1)) for e in cp["check_events"]
                                                       if e["phase"] == "opened" and e["stage"] == "effect"], "deadline_mismatch"),
    ("freshness-expired-before-dispatch", lambda cp: rebound(cp, cp["refusals"][0]["check_id"], 3600), "expired_not_past_deadline"),
    ("freshness-expired-before-dispatch", alter("refusals", "deadline", "2026-10-05T20:00:00+00:00"), "expired_refusal_deadline_mismatch"),
    ("freshness-expired-before-dispatch", lambda cp: [e.update(reasons=["check_overdue"]) for e in cp["check_events"]
                                                       if e["phase"] == "expired"], "phase_reasons_mismatch"),
    ("freshness-expired-before-dispatch", lambda cp: [e.update(age_bound_seconds=61) for e in cp["check_events"]
                                                       if e["phase"] == "completed" and e["stage"] == "effect"], "check_event_clock_drift"),
    ("freshness-applied", alter("decisions", "decided_at", "2026-10-05T19:00:09+00:00"), "evaluation_alias_mismatch"),
    ("freshness-applied", lambda cp: cp["attempts"][0].update(recorded_at="2026-10-05T18:59:00+00:00"), "recorded_before_evaluated"),
    ("freshness-applied", lambda cp: cp["decisions"][0].update(evaluated_at="2026-10-05T19:00:00"), "timestamp_invalid"),
    ("freshness-applied", lambda cp: [e.update(extension_id="ext-unknown") for e in cp["check_events"]], "extension_unknown"),
    ("freshness-applied", lambda cp: [e.__setitem__("recorded_at", "2026-10-05T18:00:00+00:00") for e in cp["check_events"][-1:]],
     "check_event_time_regression"),
    ("freshness-nonce-bound", lambda cp: [i.update(age_basis="guessed") for ch in cp["resolution_checks"] for i in ch["inputs"][1:2]],
     None),
    ("freshness-nonce-replay-refused", lambda cp: [i.update(age_basis="nonce_bound") for r in cp["refusals"]
                                                    for i in r["resolution_inputs"] if i.get("read_state") == "nonce_mismatch"],
     "nonce_mismatch_basis"),
    ("freshness-extension-accepted-and-refused", alter("age_extensions", "signer", "urn:cognous:principal:requester"),
     "accepted_extension_self_signed"),
    ("freshness-extension-accepted-and-refused", alter("age_extensions", "signer", None), "accepted_extension_unsigned"),
    ("freshness-extension-accepted-and-refused", alter("age_extensions", "to_max_age_seconds", 50), "accepted_extension_invalid"),
    ("freshness-extension-accepted-and-refused", lambda cp: rebound(cp, next(e["check_id"] for e in cp["check_events"]
                                                                              if e.get("extension_id")), 999), "extension_bound_mismatch"),
    ("freshness-extension-accepted-and-refused", lambda cp: cp["age_extension_refusals"][0].update(reasons=["age_extension_unsigned",
                                                                                                           "age_extension_invalid"]),
     "extension_refusal_reasons_not_canonical"),
    ("freshness-extension-accepted-and-refused", lambda cp: cp["age_extension_refusals"][0].update(reasons=["made_up"]), "unknown_enum_value"),
    ("freshness-overdue-recovery-run", alter("recovery_runs", "trigger", "weekly"), "unknown_enum_value"),
    ("freshness-overdue-recovery-run", alter("recovery_runs", "oldest_open_age_seconds", None), "recovery_run_oldest_age_inconsistent"),
    ("freshness-overdue-recovery-run", alter("recovery_runs", "open_count", 0), "recovery_run_oldest_age_inconsistent"),
    ("freshness-overdue-recovery-run", alter("recovery_runs", "overdue", ["no-such-check"]), "recovery_overdue_without_event"),
    ("freshness-overdue-recovery-run", lambda cp: cp["recovery_runs"].append(copy.deepcopy(cp["recovery_runs"][0])), "duplicate_recovery_run_id"),
    ("all-three-expired-before-dispatch", lambda cp: [e.update(deadline=shift(e["deadline"], 2)) for e in cp["check_events"]
                                                       if e["phase"] == "opened" and e["stage"] == "effect"], "deadline_mismatch"),
]


@pytest.mark.parametrize("name,change,code", ALTERED, ids=[f"{n}-{i}" for i, (n, _, _) in enumerate(ALTERED)])
def test_altered_profile_member_is_refused_with_a_stable_code(name, change, code):
    cp = mutate(name, change)
    if code is None:  # a value outside a closed enumeration inside a pydantic-checked row carries the structure code
        code = "unknown_enum_value"
    refused(cp, code)


# --------------------------------------------------------------------------------------- damaged: unknown member
def add(field, **members):
    def change(cp):
        rows = cp[field]
        (rows[0] if isinstance(rows, list) else rows).update(members)
    return change


UNKNOWN = [
    ("identity-applied-renewed", add("operations", note="x"), "undeclared_member"),
    ("identity-applied-renewed", add("operation_renewals", note="x"), "undeclared_member"),
    ("identity-applied-renewed", add("attempt_joins", note="x"), "undeclared_member"),
    ("identity-applied-renewed", lambda cp: first(cp["decisions"], result="authorized")["binding"]["runtime_authority"].update(
        operation_note="x"), "undeclared_member"),
    ("rules-adopted-applied", add("rule_revisions", note="x"), "undeclared_member"),
    ("rules-adopted-applied", lambda cp: cp["decisions"][0]["rule_identity"].update(extra=[]), "undeclared_member"),
    ("rules-adopted-applied", lambda cp: [v.update(extra=1) for v in cp["decisions"][0]["rule_identity"]["rules"].values()], "undeclared_member"),
    ("rules-self-signed-revision-refused", lambda cp: cp["rule_revision_refusals"][0]["revision"].update(extra=1), "undeclared_member"),
    ("freshness-applied", add("attempts", extra_clock="2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("freshness-applied", add("check_events", extra_clock="2026-10-05T19:00:00+00:00"), "undeclared_member"),
    ("freshness-applied", lambda cp: cp["resolution_checks"][0]["inputs"][1].update(extra=1), "undeclared_member"),
    ("freshness-expired-before-dispatch", add("refusals", extra_clock="x"), "undeclared_member"),
    ("freshness-extension-accepted-and-refused", add("age_extensions", note="x"), "undeclared_member"),
    ("freshness-extension-accepted-and-refused", lambda cp: cp["age_extension_refusals"][0]["extension"].update(note="x"),
     "undeclared_member"),
    ("freshness-overdue-recovery-run", add("recovery_runs", note="x"), "undeclared_member"),
    ("freshness-overdue-recovery-run", lambda cp: [e.update(phase="paused") for e in cp["check_events"][:1]], "unknown_enum_value"),
    ("freshness-nonce-bound", lambda cp: [i.update(age_basis="guessed") for i in cp["decisions"][0]["resolution_inputs"][1:2]],
     "unknown_enum_value"),
    ("identity-applied-renewed", add("operations", extensions={"no-prefix": 1}), "invalid_extension_key"),
    ("freshness-overdue-recovery-run", add("recovery_runs", extensions=[]), "schema_violation"),
    ("all-three-applied-renewed", add("attempt_joins", extensions={"Bad": 1}), "invalid_extension_key"),
]


@pytest.mark.parametrize("name,change,code", UNKNOWN, ids=[f"{n}-{i}" for i, (n, _, _) in enumerate(UNKNOWN)])
def test_unknown_profile_member_is_refused_never_dropped(name, change, code):
    refused(mutate(name, change), code)


def test_unknown_top_level_list_is_reported_unmapped_not_retained():
    cp = mutate("identity-applied-renewed", lambda cp: cp.update(operation_ledgers=[{"x": 1}]))
    bundle = do_import(cp)
    assert any(f.code == "B001" and f.path == "operation_ledgers" for f in bundle.import_reports[0].findings)
    assert bundle.status == "reconstruction_partial"
    assert not any("operation_ledgers" in r.source_path for r in bundle.records)


def test_x_extensions_are_preserved_on_profile_rows():
    cp = mutate("all-three-applied-renewed", lambda cp: (cp["operations"][0].update(extensions={"x-note": {"a": 1}}),
                                                         cp["attempt_joins"][0].update(extensions={"x-join": 2}),
                                                         cp["rule_revisions"][0].update(extensions={"x-rev": True})))
    bundle = do_import(cp)
    assert [r.data["extensions"] for r in bundle.records if r.record_type == "operation"] == [{"x-note": {"a": 1}}]
    assert [r.data["extensions"] for r in bundle.records if r.record_type == "attempt_join"] == [{"x-join": 2}]
    assert [r.data["extensions"] for r in bundle.records if r.record_type == "rule_revision"] == [{"x-rev": True}]
    again, dumped = rebuild(bundle)
    assert again["records"] == dumped["records"]


def test_damage_after_export_changes_the_retained_digest():
    """Retention is verbatim, so a profile row altered after export is caught by the content digest (and by re-validation when
    it breaks a rule above), not silently absorbed."""
    from agent_replay_bundle import content_digest
    bundle = do_import(run("freshness-extension-accepted-and-refused"))
    before = content_digest(bundle).value
    for record in bundle.records:
        if record.record_type == "age_extension":
            record.data["signer"] = "urn:cognous:principal:someone"
    assert content_digest(bundle).value != before


def test_dropped_retained_profile_record_fails_revalidation():
    bundle = do_import(run("all-three-expired-before-dispatch"))
    dumped = bundle.model_dump(mode="json")
    dumped["records"] = [r for r in dumped["records"] if r["record_type"] != "attempt_join"]
    by = lambda kind: [r["data"] for r in dumped["records"] if r["record_type"] == kind]
    cp = {"run_id": dumped["run_id"], "decisions": by("runtime_decision"), "attempts": by("control_plane_attempt_transition"),
          "observations": by("effect_observation"), "reconciliations": by("reconciliation")}
    refused(extend_retained_inputs(cp, dumped), "attempt_without_join")


def test_pack_end_to_end_freshness_block_when_the_pack_knows_the_generation():
    """Replay -> Evidence Pack: a freshness-on bundle flows to the pack's opt-in freshness block. Active only where the installed
    pack lists the programme-2 generation (it does not yet: see the hand-back of stream P3)."""
    imp = pytest.importorskip("agent_governance_evidence_pack.importer")
    if not hasattr(imp, "P2_REVISIONS"):
        pytest.skip("installed Evidence Pack does not list the programme-2 generation")
    manifest = {"manifest_version": "1.1", "manifest_id": "m",
                "actions": [{"action_id": "a", "review_requirement": "none", "reliance_requirement": "none"}], "tools": []}
    bundle = do_import(run("all-three-expired-before-dispatch")).model_dump(mode="json")
    pack = imp.import_manifest_reconstruction(manifest, bundle, generated_at="2026-10-05T19:05:00+00:00")
    block = pack.metadata["traceable_import"]["freshness_summary"]
    assert block["expired_before_dispatch_count"] == 1 and block["refusal_rows_expired_before_dispatch"] == 1
    live = imp.import_manifest_reconstruction(manifest, do_import(run("freshness-live-overdue-check")).model_dump(mode="json"),
                                              generated_at="2026-10-05T19:05:00+00:00").metadata["traceable_import"]["freshness_summary"]
    assert (live["open_count"], live["overdue_count"], live["recovery_run_count"]) == (1, 1, 1)
    abandoned = imp.import_manifest_reconstruction(manifest, do_import(run("freshness-reaper-after-decision")).model_dump(mode="json"),
                                                   generated_at="2026-10-05T19:05:00+00:00").metadata["traceable_import"]["freshness_summary"]
    assert (abandoned["abandoned_open_count"], abandoned["recovery_run_count"]) == (1, 2)
    off = imp.import_manifest_reconstruction(manifest, do_import(run("default-path")).model_dump(mode="json"),
                                             generated_at="2026-10-05T19:05:00+00:00")
    assert "freshness_summary" not in off.metadata["traceable_import"]
