"""Consumer conformance of Replay to the ODES execution-attempt lifecycle contract (0.1.0-draft, level L).

The contract (vendored under tests/contracts/execution-attempt-lifecycle/, ODES d1e17fa1) ships abstract fixtures
with synthetic ids. This module feeds every vendored fixture through Replay's real import code and records the
outcome of each one in a generated table (also kept in docs/contract-conformance-execution-attempt-lifecycle.md):

* ACCEPTED / REFUSED  Replay did what the fixture requires (a refusal must also match the agreed message pattern).
* DIVERGES            Replay does something else; the test is a strict xfail that states the contract expectation.
* NOT-EXERCISED       the adapter cannot reach the rule; the test asserts that limitation and its reason.

Replay never emits contract codes, so CODE_TO_REPLAY is the agreed mapping from each contract refusal code to the
message pattern Replay is expected to raise (``emitted=False`` marks a rule Replay does not implement yet; its
pattern is the proposed wording, not an existing message).

Adapters (never weaken a fixture to make it pass):

* executor family (attempts / attempt_events / execution_result): the fixture's rows, events and result members
  are planted over a real captured export (tests/fixtures/route_b_post_commit/ for recovery reports,
  tests/fixtures/security_runtime_valid/ for validated observations) and imported through
  ``import_bounded_workflow`` together with the real Control Plane run.
* control_plane_attempts: the rows replace ``attempts`` of the real Control Plane run (journal/lifecycle validator
  ``_validate_repaired_run``).
* resolution_journal / resolution_checks: they replace ``check_events`` / ``resolution_checks`` of the real run
  (``refusal_evidence.validate_run``).

Adapter completions are limited to data Replay needs and the contract leaves abstract: synthetic ids and the
synthetic observation time are rebound to the base capture's, the attempt row gets the base row's
``operation_digest`` / ``created_at``, a validated applied observation gets the base destination_state when the
fixture's is absent or ``{}``, and ``observations`` is mirrored from the result when the fixture has no such member
(Replay requires it). Every refused fixture is paired with a control: the same document with only the planted
defect repaired is accepted by the same adapter.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import types
from pathlib import Path

import pytest

from agent_replay_bundle import importers as I
from agent_replay_bundle.importers import ImportContractError, import_bounded_workflow

HERE = Path(__file__).parent
CONTRACT_DIR = HERE / "contracts" / "execution-attempt-lifecycle"
BASES = HERE / "fixtures"
DOC = HERE.parent / "docs" / "contract-conformance-execution-attempt-lifecycle.md"

CONTRACT_NAME = "execution-attempt-lifecycle"
CONTRACT_VERSION = "0.1.0-draft"
ODES_COMMIT = "d1e17fa155140f371050aff4b61da0f2cc84f44a"
REVISION = I.CONTROL_PLANE_F5B_REVISION
EXECUTOR_REVISION = I.MOLTBOT_F5B_REVISION


# ---------------------------------------------------------------------------------------------------------
# 1. Drift check
# ---------------------------------------------------------------------------------------------------------

def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vendored_contract_has_not_drifted():
    manifest = json.loads((CONTRACT_DIR / "CONTRACT.json").read_text(encoding="utf-8"))
    assert manifest["contract"] == CONTRACT_NAME
    assert manifest["contract_version"] == CONTRACT_VERSION
    assert manifest["odes_commit"] == ODES_COMMIT
    assert manifest["role"] == "consumer"
    assert manifest["conformance_level"] == "L"
    listed = manifest["files"]
    on_disk = sorted(p.relative_to(CONTRACT_DIR).as_posix() for p in CONTRACT_DIR.rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.name != "CONTRACT.json")
    problems = []
    for name in sorted(set(listed) - set(on_disk)):
        problems.append(f"missing: {name}")
    for name in sorted(set(on_disk) - set(listed)):
        problems.append(f"unlisted: {name}")
    for name in sorted(set(listed) & set(on_disk)):
        if _digest(CONTRACT_DIR / name) != listed[name]:
            problems.append(f"modified: {name}")
    assert not problems, "vendored contract differs from CONTRACT.json: " + "; ".join(problems)


# ---------------------------------------------------------------------------------------------------------
# Contract refusal code -> Replay message pattern (agreed mapping)
# ---------------------------------------------------------------------------------------------------------

class Mapped:
    def __init__(self, pattern: str, emitted=True, note: str = ""):  # emitted: True, False or "partly"
        self.pattern, self.emitted, self.note = pattern, emitted, note


CODE_TO_REPLAY = {
    # executor rows
    "attempt_without_events": Mapped(r"executor attempt .* has no attempt events"),
    "duplicate_attempt_row": Mapped(r"duplicate executor attempt row"),
    "missing_start_event": Mapped(r"executor attempt .* events do not start with attempted"),
    "repeated_start_event": Mapped(r"executor attempt .* repeats its attempted event"),
    "event_order": Mapped(r"attempt_events\[\d+\] (event_id is repeated or out of order|created_at is missing or out of order)"),
    "terminal_event_missing": Mapped(r"execution result status .* contradicts the terminal attempt event",
                                     note="Replay does not distinguish a missing terminal event from a mismatched one"),
    "status_terminal_mismatch": Mapped(r"execution result status .* contradicts the terminal attempt event"),
    # observations and recovery
    "observations_mismatch": Mapped(r"accepted executor observations differ from result",
                                    note="Replay requires the recovery report to be mirrored in observations (legacy layout)"),
    "recovery_observations_mismatch": Mapped(r"recovery_observations differ from the result report", emitted=False,
                                             note="Replay does not know the member"),
    "recovery_observation_status": Mapped(r"a recovery report is only carried by results unknown or observed"),
    "recovery_retry_eligible": Mapped(r"unsupported retry eligibility"),
    "recovery_report_incomplete": Mapped(r"(operation_digest|claim_state|effect_id|reason) is required for an? \w+ recovery report"),
    "effect_free_reconcile_claims_attempt": Mapped(r"an effect-free reconcile result cannot claim an attempt"),
    "recovery_state_mismatch": Mapped(r"recovery report observed-state contradiction"),
    "unknown_state_mismatch": Mapped(r"recovery report observed-state contradiction|null observation cannot establish observed state"),
    "unknown_with_validated_observation": Mapped(r"unknown result cannot carry a validated observation", emitted=False,
                                                 note="no Replay rule; see finding"),
    # member model
    "undeclared_member": Mapped(r"has unsupported member\(s\)|recovery report has undeclared members"),
    "invalid_extension_key": Mapped(r"extensions names must start with 'x-'"),
    "schema_violation": Mapped(r"recovery report in observations \(legacy layout\)", emitted=False,
                               note="Replay has no schema layer; for the legacy layout the proposed wording is used"),
    "unknown_enum_value": Mapped(r"is not a recovery status|is not a declared (status|value)", emitted="partly",
                                 note="Replay checks only the recovery report status (the rest uses the proposed wording)"),
    "unsupported_contract_version": Mapped(r"contract_version", emitted=False,
                                           note="Replay exports carry no contract_version member; out of scope"),
    # Control Plane attempts
    "missing_start_record": Mapped(r"lifecycle lacks its attempted start record"),
    "invalid_reconciled_marker": Mapped(r"invalid reconciled_existing marker"),
    "repeated_record": Mapped(r"lifecycle repeats a record"),
    # resolution journal and checks
    "journal_protocol": Mapped(r"journal (missing opening or already closed|binding changed|input missing)|duplicate journal opening"),
    "journal_unbound_completion": Mapped(r"completed journal differs from actual resolution check"),
    "journal_check_reused": Mapped(r"completed journals reuse one actual resolution check"),
    "duplicate_check_id": Mapped(r"duplicate/empty resolution check id"),
    "resolution_checks_out_of_order": Mapped(r"resolution checks are out of journal order"),
}


def test_every_contract_code_has_a_mapping():
    source = (CONTRACT_DIR / "validate.py").read_text(encoding="utf-8")
    codes = set(re.findall(r'Violation\("([a-z_]+)"', source))
    assert codes == set(CODE_TO_REPLAY), (
        f"unmapped: {sorted(codes - set(CODE_TO_REPLAY))}; stale: {sorted(set(CODE_TO_REPLAY) - codes)}")


# ---------------------------------------------------------------------------------------------------------
# Fixtures and bases
# ---------------------------------------------------------------------------------------------------------

def load_fixtures():
    out = {}
    for kind in ("valid", "invalid"):
        for path in sorted((CONTRACT_DIR / "fixtures" / kind).glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                assert data["fixture_id"] == path.stem
            except (ValueError, KeyError, AssertionError, TypeError):
                continue  # a damaged or foreign file is reported by the drift test, not by a collection error
            out[data["fixture_id"]] = data
    return out


FIXTURES = load_fixtures()


def _read(directory: str):
    d = BASES / directory
    return (json.loads((d / "control_plane_run.json").read_text()),
            json.loads((d / "proposal.json").read_text()),
            json.loads((d / "executor.json").read_text()))


def load_security():
    cp, proposal, x = _read("security_runtime_valid")
    x["repository"]["revision"] = EXECUTOR_REVISION
    x["provenance"]["source_asserted"]["repository_revision"] = EXECUTOR_REVISION
    return cp, proposal, x


def load_route_b(name: str):
    return _read("route_b_post_commit/" + name)


class NotExercised(Exception):
    """The adapter cannot reach the rule the fixture exercises (the message is the reason)."""


class Outcome:
    def __init__(self, accepted: bool, message: str = "", crash: bool = False):
        self.accepted, self.message, self.crash = accepted, message, crash


def run_import(cp, proposal, executor=None) -> Outcome:
    try:
        bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=executor, control_plane_revision=REVISION)
    except ImportContractError as exc:
        return Outcome(False, str(exc))
    except Exception as exc:  # a crash is not a refusal
        return Outcome(False, f"{type(exc).__name__}: {exc}", crash=True)
    return Outcome(True, bundle.status)


def _is_recovery(observation) -> bool:
    return isinstance(observation, dict) and "state" not in observation and "status" in observation


def _rebind(value, table):
    if isinstance(value, dict):
        return {k: _rebind(v, table) for k, v in value.items()}
    if isinstance(value, list):
        return [_rebind(v, table) for v in value]
    if isinstance(value, str):
        return table.get(value, value)
    return value


SYN_DIGEST = "sha256:" + "d" * 64
SYN_OBSERVED_AT = "2026-01-01T00:00:05Z"


def _table(cp, x):
    envelope = x["execution_envelope"]
    return {
        "syn-attempt-1": x["attempts"][0]["attempt_id"],
        "syn-effect-1": envelope["effect_id"],
        "syn-decision-1": envelope["decision_id"],
        SYN_DIGEST: I._sha256(envelope["operation"]),
        SYN_OBSERVED_AT: "2026-10-05T19:00:00+00:00",
    }


# ---- adapter: executor family -----------------------------------------------------------------------------

def _complete_destination_state(observation, base_destination):
    if (isinstance(observation, dict) and observation.get("state") in {"applied", "partial"}
            and observation.get("destination_state") in (None, {})):
        observation = dict(observation)
        observation["destination_state"] = {**base_destination, "state": observation["state"]}
    return observation


def _make_route_c_unobserved(cp, x, table):
    """Route C when the Control Plane observation is unavailable: the reconciliation is rejected/held and the
    executor reports result 'unknown' with no observation (an acknowledged but unobserved delivery)."""
    effect = x["execution_envelope"]["effect_id"]
    when = "2026-10-05T19:00:00+00:00"
    rec = {"effect_id": effect, "reconciled_at": when, "result": "hold", "observation": None,
           "observation_accepted": False, "retry_eligible": False, "reasons": ["observation_unavailable"],
           "evaluation_time": when, "observation_max_age_seconds": 300, "observation_clock_tolerance_seconds": 5}
    cp["reconciliations"][-1] = rec
    cp["observations"] = [r["observation"] for r in cp["reconciliations"] if r["observation_accepted"]]
    attempt = copy.deepcopy(x["control_plane_attempts"][0])
    attempt["acknowledgement"] = {"moltbot_safe_status": "executed", "attempt_id": table["syn-attempt-1"],
                                  "newly_executed": False}
    cp["attempts"][-1] = attempt
    evidence = {"attempt": attempt, "reconciliation": rec}
    x["control_plane_attempts"] = [attempt]
    x["control_plane_evidence"] = evidence
    return evidence


def build_executor(doc, mirror_observations=True):
    result = doc["execution_result"]
    observation = result.get("observation")
    if _is_recovery(observation):
        if result["status"] == "observed":
            base = "reconcile_only"
        elif observation["status"] in {"applied", "partial"}:
            base = "observe_bound_fail"
        else:
            base = "lost_ack_recon_down"
        cp, proposal, x = load_route_b(base)
        if observation["status"] == "hold":
            x["effects"] = []  # a hold report establishes no destination state
    else:
        cp, proposal, x = load_security()
    table = _table(cp, x)
    base_attempt_row = x["attempts"][0]
    base_destination = load_security()[2]["observations"][0]["destination_state"]

    planted = _rebind(doc, table)
    x["attempts"] = [{**base_attempt_row, **row} for row in planted["attempts"]]
    x["attempt_events"] = planted["attempt_events"]
    res = {**x["execution_result"], **planted["execution_result"]}
    res["observation"] = _complete_destination_state(planted["execution_result"].get("observation"), base_destination)
    x["execution_result"] = res
    if "observations" in planted:
        x["observations"] = [_complete_destination_state(o, base_destination) for o in planted["observations"]]
    elif mirror_observations:
        x["observations"] = [copy.deepcopy(res["observation"])] if res["observation"] else []
    else:
        x.pop("observations", None)
    for member in ("recovery_observations", "extensions"):
        if member in planted:
            x[member] = planted[member]
    if res["observation"] is None:
        res["control_plane_evidence"] = _make_route_c_unobserved(cp, x, table)
    return lambda: run_import(cp, proposal, x)


def build_cp_attempts(doc):
    cp, proposal, x = load_security()
    cp["attempts"] = _rebind(doc["control_plane_attempts"], _table(cp, x))
    return lambda: run_import(cp, proposal)


def build_resolution(doc):
    cp, proposal, _ = load_security()
    cp["check_events"] = copy.deepcopy(doc["resolution_journal"])
    cp["resolution_checks"] = copy.deepcopy(doc["resolution_checks"])
    return lambda: run_import(cp, proposal)


def evaluate_doc(doc) -> Outcome:
    if "control_plane_attempts" in doc:
        build = build_cp_attempts
    elif "resolution_journal" in doc:
        build = build_resolution
    else:
        build = build_executor
    return build(doc)()


def evaluate(fixture) -> Outcome:
    reason = NOT_EXERCISED.get(fixture["fixture_id"])
    if reason:
        raise NotExercised(reason)
    return evaluate_doc(fixture["document"])


# ---------------------------------------------------------------------------------------------------------
# 3. The status of every fixture
# ---------------------------------------------------------------------------------------------------------

NOT_EXERCISED = {
    "executor-terminal-failed-vs-status": (
        "result executed with observation null is refused first by a Replay-only rule (importers.py:1384-1385, "
        "an attempt without a validated observation must remain unknown), so the terminal-event rule is "
        "unreachable without replacing the fixture's explicit observation null (not done). The rule itself is "
        "exercised by executor-dropped-terminal-event and by test_audit_defect_detection.py"),
}

# fixture id -> finding ids / note shown in the table
NOTES = {
    "control-plane-normal-attempted-acknowledged":
        "F-P2-RP-2: started_at differs between the two rows; Replay treats it as an attempt invariant",
    "executor-normal-attempted-executed-observed":
        "F-P2-RP-1: result observed with attempted/acknowledged/newly_executed true is refused",
    "executor-normal-observations-member":
        "F-P2-RP-3: refused first for the unknown member recovery_observations; with it removed, F-P2-RP-1 refuses it",
    "executor-unknown-recovery-separate-member-route-b":
        "F-P2-RP-3 (member recovery_observations); without it F-P2-RP-4 (observations [] is refused)",
    "executor-unknown-with-validated-observation":
        "F-P2-RP-6: no rule; refused only by the terminal-event rule, accepted when the terminal event is unknown",
    "recovery-observations-differs-from-result":
        "F-P2-RP-3: refused only because the member is unknown; no mismatch rule exists",
    "recovery-report-in-observations-member":
        "F-P2-RP-5: legacy layout is the layout Replay requires, so it is accepted",
    "result-status-unknown-enum-value":
        "F-P2-RP-7: refused only because a recovery report needs unknown/observed; a consistent unknown status is accepted",
    "executor-terminal-failed-vs-status": "see reason",
    "extension-namespace-member-preserved":
        "accepted; top-level extensions are not retained (F-P2-RP-12)",
    "extension-key-without-x-prefix":
        "rule order: refused here before F-P2-RP-1 would be",
    "undeclared-member-outside-extensions":
        "rule order: refused here before F-P2-RP-1 would be",
}


def classify(fixture):
    """Return (status, Outcome | None)."""
    try:
        outcome = evaluate(fixture)
    except NotExercised:
        return "NOT-EXERCISED", None
    if fixture["expected_outcome"] == "accept":
        return ("ACCEPTED" if outcome.accepted else "DIVERGES"), outcome
    mapped = CODE_TO_REPLAY[fixture["expected_refusal"]]
    ok = (not outcome.accepted and not outcome.crash and re.search(mapped.pattern, outcome.message) is not None)
    return ("REFUSED" if ok else "DIVERGES"), outcome


DECLARED = {
    "control-plane-normal-attempted-acknowledged": "DIVERGES",
    "control-plane-reconciled-existing-acknowledged": "ACCEPTED",
    "control-plane-reconciled-existing-partial": "ACCEPTED",
    "executor-normal-attempted-executed-observed": "DIVERGES",
    "executor-normal-observations-member": "DIVERGES",
    "executor-observed-effect-free-reconcile-route-b": "ACCEPTED",
    "executor-unknown-ack-unobserved": "ACCEPTED",
    "executor-unknown-recovery-hold-route-b": "ACCEPTED",
    "executor-unknown-recovery-observation-route-b": "ACCEPTED",
    "executor-unknown-recovery-separate-member-route-b": "DIVERGES",
    "executor-unknown-recovery-unavailable-route-b": "ACCEPTED",
    "extension-namespace-member-preserved": "ACCEPTED",
    "resolution-checks-overlap-a-completes-first": "ACCEPTED",
    "resolution-checks-overlap-b-completes-first-listed-completion-order": "ACCEPTED",
    "resolution-checks-overlap-b-completes-first-listed-open-order": "ACCEPTED",
    "control-plane-dropped-start-record": "REFUSED",
    "control-plane-start-row-reconciled-existing-false": "REFUSED",
    "effect-free-reconcile-claims-attempt": "REFUSED",
    "effect-free-reconcile-state-mismatch": "REFUSED",
    "executor-dropped-start-event": "REFUSED",
    "executor-dropped-terminal-event": "REFUSED",
    "executor-terminal-failed-vs-status": "NOT-EXERCISED",
    "executor-unknown-recovery-state-contradiction": "REFUSED",
    "executor-unknown-with-validated-observation": "DIVERGES",
    "extension-key-without-x-prefix": "REFUSED",
    "recovery-applied-missing-operation-digest": "REFUSED",
    "recovery-hold-missing-reason": "REFUSED",
    "recovery-observations-differs-from-result": "DIVERGES",
    "recovery-report-in-observations-member": "DIVERGES",
    "recovery-retry-eligible-true": "REFUSED",
    "resolution-checks-sequential-reorder": "REFUSED",
    "result-status-unknown-enum-value": "DIVERGES",
    "undeclared-member-outside-extensions": "REFUSED",
}


def _fixture_params():
    params = []
    for fid in FIXTURES:
        marks = []
        if DECLARED[fid] == "DIVERGES":
            marks.append(pytest.mark.xfail(strict=True, reason=NOTES[fid]))
        params.append(pytest.param(fid, marks=marks, id=fid))
    return params


def test_declared_statuses_cover_every_fixture_and_match_the_adapters():
    assert set(DECLARED) == set(FIXTURES)
    assert len(FIXTURES) == 33
    actual = {fid: classify(fx)[0] for fid, fx in FIXTURES.items()}
    assert actual == DECLARED


# ---------------------------------------------------------------------------------------------------------
# 2. Consumer conformance: one test per fixture
# ---------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("fid", _fixture_params())
def test_vendored_fixture_through_replay(fid):
    """ACCEPTED/REFUSED pass; DIVERGES are strict xfails stating the contract expectation."""
    fixture = FIXTURES[fid]
    if DECLARED[fid] == "NOT-EXERCISED":
        with pytest.raises(NotExercised) as info:
            evaluate(fixture)
        assert str(info.value) == NOT_EXERCISED[fid]
        return
    outcome = evaluate(fixture)
    assert not outcome.crash, f"Replay crashed instead of refusing: {outcome.message}"
    if fixture["expected_outcome"] == "accept":
        assert outcome.accepted, f"contract-valid fixture refused by Replay: {outcome.message}"
        return
    mapped = CODE_TO_REPLAY[fixture["expected_refusal"]]
    assert not outcome.accepted, f"contract-invalid fixture ({fixture['expected_refusal']}) accepted by Replay"
    assert re.search(mapped.pattern, outcome.message), (
        f"refused, but not as {fixture['expected_refusal']}: {outcome.message!r} does not match {mapped.pattern!r}")


def _harmonize_started_at(doc):
    rows = doc["control_plane_attempts"]
    for row in rows:
        row["started_at"] = rows[0]["started_at"]


def _repair_cp_dropped_start(doc):
    rows = doc["control_plane_attempts"]
    rows.insert(0, {**rows[0], "status": "attempted", "acknowledgement": {}})
    _harmonize_started_at(doc)


def _repair_cp_marker(doc):
    doc["control_plane_attempts"][0]["acknowledgement"] = {}
    _harmonize_started_at(doc)


def _as_executed(doc):
    doc["execution_result"]["status"] = "executed"


def _repair_extension_key(doc):
    doc["extensions"] = {"x-trace": doc["extensions"]["trace"]}
    _as_executed(doc)


def _repair_undeclared(doc):
    doc["execution_result"].pop("injected_member")
    _as_executed(doc)


# Repair of ONLY the planted defect. extension-key / undeclared-member also set result status executed in the
# control, because their fixture shape (result observed + attempted true) is refused by F-P2-RP-1 on its own.
REPAIRS = {
    "control-plane-dropped-start-record": _repair_cp_dropped_start,
    "control-plane-start-row-reconciled-existing-false": _repair_cp_marker,
    "effect-free-reconcile-claims-attempt": lambda d: d["execution_result"].__setitem__("attempted", False),
    "effect-free-reconcile-state-mismatch": lambda d: d["execution_result"].__setitem__("observed_state", "applied"),
    "executor-dropped-start-event": lambda d: d["attempt_events"].insert(
        0, {"event_id": 1, "attempt_id": "syn-attempt-1", "status": "attempted", "error": None, "created_at": 1000.0}),
    "executor-dropped-terminal-event": lambda d: d["attempt_events"].append(
        {"event_id": 2, "attempt_id": "syn-attempt-1", "status": "executed", "error": None, "created_at": 1001.0}),
    "executor-unknown-recovery-state-contradiction": lambda d: d["execution_result"].__setitem__("observed_state", "unknown"),
    "extension-key-without-x-prefix": _repair_extension_key,
    "recovery-applied-missing-operation-digest": lambda d: d["execution_result"]["observation"].__setitem__(
        "operation_digest", SYN_DIGEST),
    "recovery-hold-missing-reason": lambda d: d["execution_result"]["observation"].__setitem__(
        "reason", "no_durable_effect_for_claim"),
    "recovery-retry-eligible-true": lambda d: d["execution_result"]["observation"].__setitem__("retry_eligible", False),
    "resolution-checks-sequential-reorder": lambda d: d["resolution_checks"].reverse(),
    "undeclared-member-outside-extensions": _repair_undeclared,
}


def test_every_refused_fixture_has_a_control():
    refused = {fid for fid, status in DECLARED.items() if status == "REFUSED"}
    assert refused == set(REPAIRS)


@pytest.mark.parametrize("fid", sorted(REPAIRS))
def test_refusal_is_attributable_to_the_planted_defect(fid):
    """The same adapter accepts the fixture once only its planted defect is repaired."""
    doc = copy.deepcopy(FIXTURES[fid]["document"])
    REPAIRS[fid](doc)
    outcome = evaluate_doc(doc)
    assert outcome.accepted, f"repaired control still refused: {outcome.message}"


# ---------------------------------------------------------------------------------------------------------
# Probes beyond the fixtures (each checked against the vendored reference validator first)
# ---------------------------------------------------------------------------------------------------------

def _load_reference_validator():
    """Load the vendored validate.py from source (no bytecode is written beside the vendored copy)."""
    name = "odes_lifecycle_reference_validator"
    path = CONTRACT_DIR / "validate.py"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module.validate


REFERENCE_VALIDATE = _load_reference_validator()


def _direct_cp_validator(doc) -> Outcome:
    """Run only the Control Plane lifecycle validator (no closeout / reconciliation rules around it)."""
    try:
        I._validate_repaired_run({"attempts": doc["control_plane_attempts"], "reconciliations": [], "observations": []})
    except ImportContractError as exc:
        return Outcome(False, str(exc))
    return Outcome(True, "accepted")


def _no_observations_member(doc) -> Outcome:
    return build_executor(doc, mirror_observations=False)()


def _p(**kw):
    return kw


def _set(path, value):
    def apply(doc):
        node = doc
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return apply


def _middle_event_bogus(doc):
    doc["attempt_events"].insert(1, {"event_id": 2, "attempt_id": "syn-attempt-1", "status": "bogus", "error": None,
                                     "created_at": 1000.0})
    doc["attempt_events"][2]["event_id"] = 3


def _consistent_unknown_result_status(doc):
    doc["execution_result"]["status"] = "finished"
    doc["attempt_events"][1]["status"] = "finished"


def _cp_attempt_enum(field):
    def apply(doc):
        doc["control_plane_attempts"][1][field] = "bogus"
        _harmonize_started_at(doc)
    return apply


def _marker_on_row_status(status):
    return lambda doc: doc["control_plane_attempts"][0].__setitem__("status", status)


def _executed_null_observation(doc):
    doc["execution_result"].update(status="executed", observed_state="unknown", observation=None)


def _recovery_report_on_executed(doc):
    doc["execution_result"]["status"] = "executed"


def _validated_unknown_state(doc):
    obs = doc["execution_result"]["observation"]
    obs["state"] = "bogus"
    doc["execution_result"].update(status="executed", observed_state="bogus")
    doc["observations"] = [obs]


R_RECOVERY = "executor-unknown-recovery-observation-route-b"
R_CP = "control-plane-reconciled-existing-acknowledged"
R_TERMINAL_FAILED = "executor-terminal-failed-vs-status"
R_NORMAL = "executor-normal-attempted-executed-observed"

# id, base fixture, mutation, contract code (None = contract-valid), runner, finding (None = Replay conforms)
PROBES = [
    _p(id="undeclared-member-attempt-row", base=R_RECOVERY, mutate=_set(("attempts", 0, "injected"), 1),
       code="undeclared_member", finding="F-P2-RP-8"),
    _p(id="undeclared-member-event-row", base=R_RECOVERY, mutate=_set(("attempt_events", 1, "injected"), 1),
       code="undeclared_member", finding="F-P2-RP-8"),
    _p(id="undeclared-member-control-plane-attempt-row", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "injected"), 1), code="undeclared_member", finding="F-P2-RP-8"),
    _p(id="undeclared-member-recovery-report", base=R_RECOVERY,
       mutate=_set(("execution_result", "observation", "injected"), 1), code="undeclared_member", finding=None,
       alt={"schema_violation"}),
    _p(id="extension-bad-key-attempt-row", base=R_RECOVERY,
       mutate=_set(("attempts", 0, "extensions"), {"trace": 1}), code="invalid_extension_key", finding="F-P2-RP-8"),
    _p(id="extension-bad-key-result", base=R_RECOVERY,
       mutate=_set(("execution_result", "extensions"), {"trace": 1}), code="invalid_extension_key", finding=None),
    _p(id="reconciled-marker-extra-acknowledgement-member", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "acknowledgement", "x"), 1), code="invalid_reconciled_marker",
       runner=_direct_cp_validator, finding=None),
    _p(id="reconciled-marker-non-boolean", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "acknowledgement"), {"reconciled_existing": "yes"}),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding=None),
    _p(id="reconciled-marker-on-failed-row", base=R_CP, mutate=_marker_on_row_status("failed"),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding="F-P2-RP-9"),
    _p(id="reconciled-marker-on-unknown-row", base=R_CP, mutate=_marker_on_row_status("unknown"),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding="F-P2-RP-9"),
    _p(id="enum-result-and-terminal-event-status", base=R_NORMAL,
       mutate=lambda d: (_as_executed(d), _consistent_unknown_result_status(d)), code="unknown_enum_value",
       finding="F-P2-RP-7"),
    _p(id="enum-middle-event-status", base=R_RECOVERY, mutate=_middle_event_bogus, code="unknown_enum_value",
       finding="F-P2-RP-7"),
    _p(id="enum-control-plane-attempt-status", base="control-plane-normal-attempted-acknowledged",
       mutate=_cp_attempt_enum("status"), code="unknown_enum_value", finding="F-P2-RP-7"),
    _p(id="enum-control-plane-time-source", base="control-plane-normal-attempted-acknowledged",
       mutate=_cp_attempt_enum("time_source"), code="unknown_enum_value", finding="F-P2-RP-7"),
    _p(id="enum-recovery-status", base=R_RECOVERY,
       mutate=_set(("execution_result", "observation", "status"), "bogus"), code="unknown_enum_value",
       finding=None),
    _p(id="enum-validated-observation-state", base=R_NORMAL, mutate=_validated_unknown_state,
       code="unknown_enum_value", finding="F-P2-RP-7"),
    _p(id="recovery-report-on-executed-result", base=R_RECOVERY, mutate=_recovery_report_on_executed,
       code="recovery_observation_status", finding=None),
    _p(id="executed-result-with-null-observation", base=R_TERMINAL_FAILED,
       mutate=lambda d: (d["attempt_events"][1].__setitem__("status", "executed"), _executed_null_observation(d)),
       code=None, finding="F-P2-RP-10"),
    _p(id="export-without-observations-member", base=R_RECOVERY, mutate=lambda d: None, code=None,
       runner=_no_observations_member, finding="F-P2-RP-11"),
]


def _probe_doc(probe):
    doc = copy.deepcopy(FIXTURES[probe["base"]]["document"])
    probe["mutate"](doc)
    return doc


def _probe_status(probe):
    return "DIVERGES" if probe["finding"] else ("ACCEPTED" if probe["code"] is None else "REFUSED")


def _probe_params():
    params = []
    for probe in PROBES:
        marks = []
        if probe["finding"]:
            marks.append(pytest.mark.xfail(strict=True, reason=probe["finding"]))
        params.append(pytest.param(probe, marks=marks, id=probe["id"]))
    return params


@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p["id"])
def test_probe_is_what_the_vendored_reference_validator_says(probe):
    codes = {v.code for v in REFERENCE_VALIDATE(_probe_doc(probe))}
    if probe["code"] is None:
        assert not codes
    elif probe["code"] == "unknown_enum_value":
        assert "unknown_enum_value" in codes or "schema_violation" in codes  # inside a union: schema_violation
    else:
        assert probe["code"] in codes or codes & probe.get("alt", set())


@pytest.mark.parametrize("probe", _probe_params())
def test_probe_through_replay(probe):
    outcome = probe.get("runner", evaluate_doc)(_probe_doc(probe))
    assert not outcome.crash, outcome.message
    if probe["code"] is None:
        assert outcome.accepted, f"contract-valid document refused: {outcome.message}"
        return
    assert not outcome.accepted, f"contract-invalid document ({probe['code']}) accepted"
    pattern = CODE_TO_REPLAY[probe["code"]].pattern
    assert re.search(pattern, outcome.message), f"refused, but not as {probe['code']}: {outcome.message!r}"


def test_top_level_extensions_are_preserved_in_the_imported_bundle():
    """Contract: consumers preserve extension members when re-emitting. Replay validates the export-level
    ``extensions`` member and then drops it (F-P2-RP-12)."""
    doc = copy.deepcopy(FIXTURES["extension-namespace-member-preserved"]["document"])
    cp, proposal, x = load_security()
    table = _table(cp, x)
    x["extensions"] = _rebind(doc["extensions"], table)
    bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=REVISION)
    assert "x-syn-vendor.trace" in bundle.model_dump_json()


test_top_level_extensions_are_preserved_in_the_imported_bundle = pytest.mark.xfail(
    strict=True, reason="F-P2-RP-12: export-level extensions are validated, then not retained")(
        test_top_level_extensions_are_preserved_in_the_imported_bundle)


def test_attempt_row_extensions_are_preserved_in_the_imported_bundle():
    doc = copy.deepcopy(FIXTURES["extension-namespace-member-preserved"]["document"])
    cp, proposal, x = load_security()
    x["attempts"][0]["extensions"] = _rebind(doc["attempts"][0]["extensions"], _table(cp, x))
    bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=REVISION)
    record = next(r for r in bundle.records if r.record_type == "destination_attempt")
    assert record.data["extensions"] == {"x-syn-vendor.note": "kept"}


def test_unknown_enum_value_is_retained_verbatim_not_coerced(monkeypatch):
    """Where Replay accepts a status outside the closed enumeration (F-P2-RP-7), it keeps the value as given."""
    doc = _probe_doc(next(p for p in PROBES if p["id"] == "enum-result-and-terminal-event-status"))
    captured = {}
    original = import_bounded_workflow

    def spy(*args, **kwargs):
        captured["bundle"] = original(*args, **kwargs)
        return captured["bundle"]

    monkeypatch.setattr(sys.modules[__name__], "import_bounded_workflow", spy)
    assert evaluate_doc(doc).accepted
    record = next(r for r in captured["bundle"].records if r.record_type == "execution_result")
    assert record.data["status"] == "finished"


def test_recovery_observations_is_the_only_contract_export_member_replay_does_not_know():
    """The only export member the contract declares that Replay's closed export set lacks is recovery_observations."""
    schema = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))
    document_only = {"contract", "contract_version", "producer", "resolution_journal", "resolution_checks"}
    contract_members = set(schema["properties"]) - document_only
    export_members = set(I.MOLTBOT_EXPORT_MEMBERS) | {"execution_result", "attempts", "attempt_events",
                                                       "control_plane_attempts"}
    assert contract_members - export_members == {"recovery_observations"}


# ---------------------------------------------------------------------------------------------------------
# Evidence the DIVERGES notes rely on. These pin Replay's CURRENT behaviour; update them together with the fix.
# ---------------------------------------------------------------------------------------------------------

def _fixture_outcome(fid, mutate=lambda doc: None):
    doc = copy.deepcopy(FIXTURES[fid]["document"])
    mutate(doc)
    return evaluate_doc(doc)


def _observed_with_attempt_without_evidence():
    cp, proposal, x = load_security()
    x["execution_result"]["status"] = "observed"
    x["execution_result"]["control_plane_evidence"] = {}
    x["control_plane_evidence"] = {}
    x["control_plane_attempts"] = []
    cp["attempts"] = []
    return run_import(cp, proposal, x)


def test_evidence_f_p2_rp_1_observed_result_claiming_an_attempt_is_refused_with_or_without_cp_evidence():
    assert "historical local observation cannot claim CP validation" in _fixture_outcome(R_NORMAL).message
    assert "attempted execution lacks owning attempt/reconciliation" in _observed_with_attempt_without_evidence().message


def test_evidence_f_p2_rp_2_started_at_is_the_only_obstacle_for_the_normal_lifecycle():
    def harmonize(doc):
        _harmonize_started_at(doc)
    assert _fixture_outcome("control-plane-normal-attempted-acknowledged", harmonize).accepted


def test_evidence_f_p2_rp_3_and_4_layout_members():
    drop = lambda doc: doc.pop("recovery_observations")  # noqa: E731
    assert "accepted executor observations differ from result" in _fixture_outcome(
        "executor-unknown-recovery-separate-member-route-b", drop).message
    assert "historical local observation cannot claim CP validation" in _fixture_outcome(
        "executor-normal-observations-member", drop).message
    mirrored = lambda doc: doc.__setitem__("observations", [doc["execution_result"]["observation"]])  # noqa: E731
    assert _fixture_outcome("executor-unknown-recovery-separate-member-route-b",
                            lambda doc: (drop(doc), mirrored(doc))).accepted


def test_evidence_f_p2_rp_6_unknown_with_validated_observation_is_accepted_when_the_terminal_event_is_unknown():
    assert _fixture_outcome("executor-unknown-with-validated-observation",
                            lambda doc: doc["attempt_events"][1].__setitem__("status", "unknown")).accepted


# ---------------------------------------------------------------------------------------------------------
# Generated tables (kept verbatim in the doc)
# ---------------------------------------------------------------------------------------------------------

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _cell(text: str) -> str:
    text = _UUID.sub("<id>", text).replace("|", "/").replace("\n", " ")
    return text if len(text) <= 150 else text[:147] + "..."


def render_fixture_table() -> str:
    lines = ["| Fixture | Contract expects | Status | Replay does | Note |", "|---|---|---|---|---|"]
    for fid, fixture in FIXTURES.items():
        status, outcome = classify(fixture)
        expects = "accept" if fixture["expected_outcome"] == "accept" else "refuse: " + fixture["expected_refusal"]
        if status == "NOT-EXERCISED":
            does, note = "not run", NOT_EXERCISED[fid]
        else:
            does = "accepted" if outcome.accepted else outcome.message
            note = NOTES.get(fid, "")
        lines.append(f"| `{fid}` | {expects} | {status} | {_cell(does)} | {_cell(note)} |")
    return "\n".join(lines)


def render_probe_table() -> str:
    lines = ["| Probe | Contract (vendored validator) | Status | Replay does | Finding |", "|---|---|---|---|---|"]
    for probe in PROBES:
        outcome = probe.get("runner", evaluate_doc)(_probe_doc(probe))
        expects = "valid" if probe["code"] is None else probe["code"]
        does = "accepted" if outcome.accepted else outcome.message
        lines.append(f"| `{probe['id']}` | {expects} | {_probe_status(probe)} | {_cell(does)} | {probe['finding'] or ''} |")
    return "\n".join(lines)


def render_mapping_table() -> str:
    lines = ["| Contract code | Replay message pattern | Emitted by Replay | Note |", "|---|---|---|---|"]
    for code in sorted(CODE_TO_REPLAY):
        mapped = CODE_TO_REPLAY[code]
        lines.append(f"| `{code}` | `{mapped.pattern.replace('|', chr(92) + '|')}` | { {True: 'yes', False: 'no (proposed)'}.get(mapped.emitted, mapped.emitted)} | {mapped.note} |")
    return "\n".join(lines)


def _doc_section(name: str) -> str:
    text = DOC.read_text(encoding="utf-8")
    begin, end = f"<!-- BEGIN {name} -->", f"<!-- END {name} -->"
    assert begin in text and end in text, f"{DOC.name} lacks the {name} markers"
    return text.split(begin, 1)[1].split(end, 1)[0].strip("\n")


@pytest.mark.parametrize("name,render", [
    ("FIXTURE TABLE", render_fixture_table),
    ("PROBE TABLE", render_probe_table),
    ("MAPPING TABLE", render_mapping_table),
])
def test_doc_tables_match_the_generated_tables(name, render):
    assert _doc_section(name) == render(), (
        "docs/contract-conformance-execution-attempt-lifecycle.md is stale; regenerate with "
        "`PYTHONPATH=src python -m tests.test_contract_lifecycle_conformance`")


def test_status_counts_are_stated_in_the_doc():
    counts = {}
    for status in DECLARED.values():
        counts[status] = counts.get(status, 0) + 1
    line = ", ".join(f"{counts.get(s, 0)} {s}" for s in ("ACCEPTED", "REFUSED", "DIVERGES", "NOT-EXERCISED"))
    assert f"Totals: {line}." in DOC.read_text(encoding="utf-8")


if __name__ == "__main__":  # regenerate the tables for the doc
    print("<!-- BEGIN FIXTURE TABLE -->\n" + render_fixture_table() + "\n<!-- END FIXTURE TABLE -->\n")
    print("<!-- BEGIN PROBE TABLE -->\n" + render_probe_table() + "\n<!-- END PROBE TABLE -->\n")
    print("<!-- BEGIN MAPPING TABLE -->\n" + render_mapping_table() + "\n<!-- END MAPPING TABLE -->\n")
    totals = {}
    for status in DECLARED.values():
        totals[status] = totals.get(status, 0) + 1
    print("Totals: " + ", ".join(f"{totals.get(s, 0)} {s}" for s in ("ACCEPTED", "REFUSED", "DIVERGES", "NOT-EXERCISED")) + ".")
