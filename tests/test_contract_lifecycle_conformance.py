"""Consumer conformance of Replay to the ODES execution-attempt lifecycle contract (0.1.0-draft, level L).

The contract (vendored under tests/contracts/execution-attempt-lifecycle/, ODES e33d541a) ships abstract fixtures
with synthetic ids. This module feeds every vendored fixture through Replay's real import code and records the
outcome of each one in a generated table (also kept in docs/contract-conformance-execution-attempt-lifecycle.md):

* ACCEPTED / REFUSED  Replay did what the fixture requires (a refusal must also match the agreed message pattern).
* DIVERGES            Replay does something else; the test is a strict xfail that states the contract expectation.
* NOT-EXERCISED       the adapter cannot reach the rule; the test asserts that limitation and its reason.

Replay refuses with the contract's code: ``ImportContractError.code`` carries it and the message stays the
human-readable detail. CODE_TO_REPLAY maps each contract refusal code to the message pattern Replay raises; a refusal
counts only with the expected code AND a matching message (the union rule: an unknown value inside the observation
union may carry ``schema_violation`` instead of ``unknown_enum_value``, as the contract allows).

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
fixture's is absent or ``{}``, and for a denied result the capture's effect and Control Plane attempt evidence is
cleared. ``observations`` is no longer mirrored: the contract leaves it optional and Replay accepts its absence
(RP-11). Every refused fixture is paired with a control: the same document with only the planted
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
ODES_COMMIT = "e33d541a1a7def2d3e3040eeb35a6d6cd7147afb"
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
    """Replay refuses with the contract's code (``ImportContractError.code``) and a human-readable message; the
    pattern pins the message so a refusal is attributable to the rule it names."""

    def __init__(self, pattern: str, note: str = ""):
        self.pattern, self.note = pattern, note


CODE_TO_REPLAY = {
    # executor rows
    "attempt_without_events": Mapped(r"executor attempt .* has no attempt events"),
    "duplicate_attempt_row": Mapped(r"duplicate executor attempt row"),
    "missing_start_event": Mapped(r"executor attempt .* events do not start with attempted"),
    "repeated_start_event": Mapped(r"executor attempt .* repeats its attempted event"),
    "event_order": Mapped(r"attempt_events\[\d+\] (event_id is repeated or out of order|created_at is missing or out of order)"),
    "terminal_event_missing": Mapped(r"execution result status .* contradicts the terminal attempt event 'attempted'"),
    "status_terminal_mismatch": Mapped(r"execution result status .* contradicts the terminal attempt event"),
    # observations and recovery
    "observations_mismatch": Mapped(r"accepted executor observations differ from result"),
    "recovery_observations_mismatch": Mapped(r"recovery_observations differ from the result report"),
    "recovery_observation_status": Mapped(r"a recovery report is only carried by results unknown or observed"),
    "recovery_retry_eligible": Mapped(r"unsupported retry eligibility"),
    "recovery_report_incomplete": Mapped(r"(operation_digest|claim_state|effect_id|reason) is required for an? \w+ recovery report"),
    "effect_free_reconcile_claims_attempt": Mapped(r"an effect-free reconcile result cannot claim an attempt"),
    "recovery_state_mismatch": Mapped(r"recovery report observed-state contradiction"),
    "unknown_state_mismatch": Mapped(r"recovery report observed-state contradiction|null observation cannot establish observed state"),
    "unknown_with_validated_observation": Mapped(r"unknown result cannot carry a validated observation"),
    "observed_result_claims_attempt": Mapped(r"an observed result cannot claim an attempt"),
    "executed_without_observation": Mapped(r"an executed result must carry the observation"),
    # member model
    "undeclared_member": Mapped(r"has unsupported member\(s\)|recovery report has undeclared members"),
    "invalid_extension_key": Mapped(r"extensions names must start with 'x-'"),
    "schema_violation": Mapped(r"is required|must be an (object|array)|must be object or null",
                               "Replay's legacy-layout tolerance means the contract's own schema_violation fixture is "
                               "accepted (see the DIVERGES note); Replay emits this code for structural failures"),
    "unknown_enum_value": Mapped(r"is not a recovery status|is not a declared value"),
    "unsupported_contract_version": Mapped(r"contract_version",
                                           "Replay exports carry no contract_version member; out of scope"),
    # Control Plane attempts
    "missing_start_record": Mapped(r"lifecycle lacks its attempted start record"),
    "invalid_reconciled_marker": Mapped(r"invalid reconciled_existing marker"),
    "attempt_started_at_changed": Mapped(r"started_at changed between lifecycle rows|conflicting content under immutable attempt_id"),
    "repeated_record": Mapped(r"lifecycle repeats a record"),
    # resolution journal and checks
    "journal_protocol": Mapped(r"journal (missing opening or already closed|binding changed|input missing)|duplicate journal opening"),
    "journal_unbound_completion": Mapped(r"completed journal differs from actual resolution check"),
    "journal_check_reused": Mapped(r"completed journals reuse one actual resolution check"),
    "duplicate_check_id": Mapped(r"duplicate/empty resolution check id"),
    "resolution_checks_out_of_order": Mapped(r"resolution checks are out of journal order"),
}

# Codes Replay does not emit, with the reason (everything else in CODE_TO_REPLAY is emitted and asserted).
NOT_EMITTED = {"unsupported_contract_version": "Replay exports carry no contract_version member"}

# A refusal inside the observation union may carry either code (the contract: an unknown value inside a union
# may surface as schema_violation).
UNION_ALTERNATIVES = {"unknown_enum_value": {"unknown_enum_value", "schema_violation"}}


def refusal_matches(expected_code: str, outcome) -> bool:
    mapped = CODE_TO_REPLAY[expected_code]
    codes = UNION_ALTERNATIVES.get(expected_code, {expected_code})
    return (not outcome.accepted and not outcome.crash and outcome.code in codes
            and re.search(mapped.pattern, outcome.message) is not None)


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
    def __init__(self, accepted: bool, message: str = "", crash: bool = False, code: str | None = None):
        self.accepted, self.message, self.crash, self.code = accepted, message, crash, code


def run_import(cp, proposal, executor=None) -> Outcome:
    try:
        bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=executor, control_plane_revision=REVISION)
    except ImportContractError as exc:
        return Outcome(False, str(exc), code=exc.code)
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


def _make_denied(cp, x):
    """Route A policy denial: nothing was attempted, so no destination effect, Control Plane attempt or
    reconciliation evidence is exported (the capture's applied effect and attempt are not the fixture's)."""
    x["effects"] = []
    x["control_plane_attempts"] = []
    x["control_plane_evidence"] = {}
    x["execution_result"]["control_plane_evidence"] = {}


def build_executor(doc, mirror_observations=False):
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
    elif mirror_observations:  # legacy layout probes only; the contract leaves `observations` optional (RP-11)
        x["observations"] = [copy.deepcopy(res["observation"])] if res["observation"] else []
    else:
        x.pop("observations", None)
    for member in ("recovery_observations", "extensions"):
        if member in planted:
            x[member] = planted[member]
    if res["status"] == "denied":
        _make_denied(cp, x)
    elif res["observation"] is None:
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

NOT_EXERCISED: dict[str, str] = {}  # every vendored fixture is reachable through an adapter at this revision

# fixture id -> finding ids / note shown in the table
NOTES = {
    "recovery-report-in-observations-member":
        "deliberate step A: the legacy layout (report mirrored in observations) is still tolerated until step B "
        "(owner decision 1); the contract draft already refuses it (F-P2-RP-5)",
    "executor-denied-attempt-event":
        "adapter clears the capture's effect and Control Plane attempt evidence (nothing was attempted)",
    "extension-key-without-x-prefix":
        "rule order: refused here before observed_result_claims_attempt would be",
    "undeclared-member-outside-extensions":
        "rule order: refused here before observed_result_claims_attempt would be",
}


def classify(fixture):
    """Return (status, Outcome | None)."""
    try:
        outcome = evaluate(fixture)
    except NotExercised:
        return "NOT-EXERCISED", None
    if fixture["expected_outcome"] == "accept":
        return ("ACCEPTED" if outcome.accepted else "DIVERGES"), outcome
    return ("REFUSED" if refusal_matches(fixture["expected_refusal"], outcome) else "DIVERGES"), outcome


DECLARED = {fid: "ACCEPTED" if fx["expected_outcome"] == "accept" else "REFUSED" for fid, fx in FIXTURES.items()}
DECLARED["recovery-report-in-observations-member"] = "DIVERGES"  # deliberate step-A tolerance, see NOTES


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
    assert len(FIXTURES) == 37
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
    expected = fixture["expected_refusal"]
    assert not outcome.accepted, f"contract-invalid fixture ({expected}) accepted by Replay"
    assert outcome.code in UNION_ALTERNATIVES.get(expected, {expected}), (
        f"refused, but with code {outcome.code!r} instead of {expected!r}: {outcome.message!r}")
    assert re.search(CODE_TO_REPLAY[expected].pattern, outcome.message), (
        f"refused, but not as {expected}: {outcome.message!r} does not match {CODE_TO_REPLAY[expected].pattern!r}")


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
def _repair_terminal_event(doc):
    doc["attempt_events"][-1]["status"] = "executed"


def _repair_recovery_observations(doc):
    doc["recovery_observations"] = [doc["execution_result"]["observation"]]


REPAIRS = {
    "attempt-started-at-changed": _harmonize_started_at,
    "executed-without-observation": lambda d: d["execution_result"].update(status="unknown", observed_state="unknown",
                                                                         newly_executed=False),
    "executor-terminal-failed-vs-status": _repair_terminal_event,
    "executor-unknown-with-validated-observation": _as_executed,
    "observed-result-claims-attempt": _as_executed,
    "recovery-observations-differs-from-result": _repair_recovery_observations,
    "result-status-unknown-enum-value": lambda d: d["execution_result"].__setitem__("status", "unknown"),
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
        return Outcome(False, str(exc), code=exc.code)
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
       code="undeclared_member", finding=None),
    _p(id="undeclared-member-event-row", base=R_RECOVERY, mutate=_set(("attempt_events", 1, "injected"), 1),
       code="undeclared_member", finding=None),
    _p(id="undeclared-member-control-plane-attempt-row", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "injected"), 1), code="undeclared_member", finding=None),
    _p(id="undeclared-member-recovery-report", base=R_RECOVERY,
       mutate=_set(("execution_result", "observation", "injected"), 1), code="undeclared_member", finding=None,
       alt={"schema_violation"}),  # the reference validator reports the union failure as schema_violation
    _p(id="extension-bad-key-attempt-row", base=R_RECOVERY,
       mutate=_set(("attempts", 0, "extensions"), {"trace": 1}), code="invalid_extension_key", finding=None),
    _p(id="extension-bad-key-result", base=R_RECOVERY,
       mutate=_set(("execution_result", "extensions"), {"trace": 1}), code="invalid_extension_key", finding=None),
    _p(id="reconciled-marker-extra-acknowledgement-member", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "acknowledgement", "x"), 1), code="invalid_reconciled_marker",
       runner=_direct_cp_validator, finding=None),
    _p(id="reconciled-marker-non-boolean", base=R_CP,
       mutate=_set(("control_plane_attempts", 0, "acknowledgement"), {"reconciled_existing": "yes"}),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding=None),
    _p(id="reconciled-marker-on-failed-row", base=R_CP, mutate=_marker_on_row_status("failed"),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding=None),
    _p(id="reconciled-marker-on-unknown-row", base=R_CP, mutate=_marker_on_row_status("unknown"),
       code="invalid_reconciled_marker", runner=_direct_cp_validator, finding=None),
    _p(id="enum-result-and-terminal-event-status", base=R_NORMAL,
       mutate=lambda d: (_as_executed(d), _consistent_unknown_result_status(d)), code="unknown_enum_value",
       finding=None),
    _p(id="enum-middle-event-status", base=R_RECOVERY, mutate=_middle_event_bogus, code="unknown_enum_value",
       finding=None),
    _p(id="enum-control-plane-attempt-status", base="control-plane-normal-attempted-acknowledged",
       mutate=_cp_attempt_enum("status"), code="unknown_enum_value", finding=None),
    _p(id="enum-control-plane-time-source", base="control-plane-normal-attempted-acknowledged",
       mutate=_cp_attempt_enum("time_source"), code="unknown_enum_value", finding=None),
    _p(id="enum-recovery-status", base=R_RECOVERY,
       mutate=_set(("execution_result", "observation", "status"), "bogus"), code="unknown_enum_value",
       finding=None),
    _p(id="enum-validated-observation-state", base=R_NORMAL, mutate=_validated_unknown_state,
       code="unknown_enum_value", finding=None),
    _p(id="recovery-report-on-executed-result", base=R_RECOVERY, mutate=_recovery_report_on_executed,
       code="recovery_observation_status", finding=None),
    _p(id="executed-result-with-null-observation", base=R_TERMINAL_FAILED,
       mutate=lambda d: (d["attempt_events"][1].__setitem__("status", "executed"), _executed_null_observation(d)),
       code="executed_without_observation", finding=None),
    _p(id="export-without-observations-member", base=R_RECOVERY, mutate=lambda d: None, code=None,
       runner=_no_observations_member, finding=None),
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
    allowed = UNION_ALTERNATIVES.get(probe["code"], {probe["code"]}) | probe.get("alt", set())
    assert outcome.code in allowed, f"refused with code {outcome.code!r}, not {probe['code']!r}: {outcome.message!r}"
    pattern = CODE_TO_REPLAY[probe["code"]].pattern
    assert re.search(pattern, outcome.message) or probe.get("alt"), (
        f"refused, but not as {probe['code']}: {outcome.message!r}")


def test_top_level_extensions_are_preserved_in_the_imported_bundle():
    """Contract: consumers preserve extension members when re-emitting. Export-level ``extensions`` are retained
    verbatim as their own record (RP-12)."""
    doc = copy.deepcopy(FIXTURES["extension-namespace-member-preserved"]["document"])
    cp, proposal, x = load_security()
    table = _table(cp, x)
    x["extensions"] = _rebind(doc["extensions"], table)
    bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=REVISION)
    assert "x-syn-vendor.trace" in bundle.model_dump_json()
    record = next(r for r in bundle.records if r.record_type == "executor_export_extensions")
    assert record.data == x["extensions"]


def test_attempt_row_extensions_are_preserved_in_the_imported_bundle():
    doc = copy.deepcopy(FIXTURES["extension-namespace-member-preserved"]["document"])
    cp, proposal, x = load_security()
    x["attempts"][0]["extensions"] = _rebind(doc["attempts"][0]["extensions"], _table(cp, x))
    bundle = import_bounded_workflow(cp, proposal=proposal, moltbot_export=x, control_plane_revision=REVISION)
    record = next(r for r in bundle.records if r.record_type == "destination_attempt")
    assert record.data["extensions"] == {"x-syn-vendor.note": "kept"}


def test_replay_knows_every_contract_export_member():
    """Every export member the contract declares is in Replay's closed export set (recovery_observations included)."""
    schema = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))
    document_only = {"contract", "contract_version", "producer", "resolution_journal", "resolution_checks"}
    contract_members = set(schema["properties"]) - document_only
    export_members = set(I.MOLTBOT_EXPORT_MEMBERS) | {"execution_result", "attempts", "attempt_events",
                                                       "control_plane_attempts"}
    assert contract_members - export_members == set()


def test_replay_enumerations_equal_the_contract_enumerations():
    schema = json.loads((CONTRACT_DIR / "schema.json").read_text(encoding="utf-8"))
    defs = schema["$defs"]
    assert I.ATTEMPT_EVENT_STATUSES == set(defs["attempt_event"]["properties"]["status"]["enum"])
    assert I.EXECUTION_RESULT_STATUSES == set(defs["execution_result"]["properties"]["status"]["enum"])
    assert I.VALIDATED_OBSERVATION_STATES == set(defs["validated_observation"]["properties"]["state"]["enum"])
    assert I.RECOVERY_OBSERVATION_STATUSES == set(defs["recovery_observation"]["properties"]["status"]["enum"])
    assert I.CONTROL_PLANE_ATTEMPT_STATUSES == set(defs["control_plane_attempt"]["properties"]["status"]["enum"])
    assert I.CONTROL_PLANE_TIME_SOURCES == set(defs["control_plane_attempt"]["properties"]["time_source"]["enum"])
    assert I.EXECUTOR_ATTEMPT_MEMBERS == set(defs["executor_attempt"]["properties"])
    assert I.ATTEMPT_EVENT_MEMBERS == set(defs["attempt_event"]["properties"])
    assert I.CONTROL_PLANE_ATTEMPT_MEMBERS == set(defs["control_plane_attempt"]["properties"])
    assert I.RECOVERY_OBSERVATION_KEYS == set(defs["recovery_observation"]["properties"])
    assert I.MOLTBOT_EXECUTION_RESULT_MEMBERS == set(defs["execution_result"]["properties"])
    assert I.EXTENSION_NAME.pattern == defs["extensions"]["propertyNames"]["pattern"]


# ---------------------------------------------------------------------------------------------------------
# Behaviours added by the P3 alignment (each paired with what the vendored reference validator says)
# ---------------------------------------------------------------------------------------------------------

def _contract_codes(doc):
    return {v.code for v in REFERENCE_VALIDATE(doc)}


def test_import_contract_error_carries_a_code_and_keeps_the_message():
    err = ImportContractError("some message")
    assert err.code is None and str(err) == "some message" and isinstance(err, ValueError)
    err = ImportContractError("another", "undeclared_member")
    assert err.code == "undeclared_member" and str(err) == "another"


def test_every_mapped_code_is_emitted_by_the_importer():
    """Each contract code Replay claims to emit appears as a literal in the importer sources."""
    text = "".join((Path(I.__file__).parent / name).read_text(encoding="utf-8")
                   for name in ("importers.py", "refusal_evidence.py"))
    for code in sorted(set(CODE_TO_REPLAY) - set(NOT_EMITTED)):
        assert re.search(r"""["']%s["']""" % code, text), f"Replay never emits {code}"


LEGACY_PROBE = "executor-unknown-recovery-observation-route-b"


def _import_bundle(doc, mirror=False):
    captured = {}
    original = I.import_bounded_workflow

    def spy(*a, **k):
        captured["bundle"] = original(*a, **k)
        return captured["bundle"]

    mod = sys.modules[__name__]
    old = mod.import_bounded_workflow
    mod.import_bounded_workflow = spy
    try:
        outcome = build_executor(doc, mirror_observations=mirror)()
    finally:
        mod.import_bounded_workflow = old
    assert outcome.accepted, outcome.message
    return captured["bundle"]


def test_new_layout_retains_the_recovery_report_from_recovery_observations():
    doc = copy.deepcopy(FIXTURES["executor-unknown-recovery-separate-member-route-b"]["document"])
    assert not _contract_codes(doc)
    bundle = _import_bundle(doc)
    reports = [r for r in bundle.records if r.record_type == "executor_recovery_report"]
    assert [r.source_path for r in reports] == ["moltbot.recovery_observations[0]"]
    assert not any(r.record_type == "executor_observation" for r in bundle.records)


def test_new_layout_without_the_optional_member_still_retains_the_recovery_report():
    doc = copy.deepcopy(FIXTURES[LEGACY_PROBE]["document"])
    doc.pop("recovery_observations", None)
    doc.pop("observations", None)
    assert not _contract_codes(doc)
    reports = [r for r in _import_bundle(doc).records if r.record_type == "executor_recovery_report"]
    assert [r.source_path for r in reports] == ["moltbot.execution_result.observation"]


def test_legacy_layout_is_still_tolerated_and_retained_as_before():
    """Step A: the recovery report mirrored in ``observations`` is accepted until the runtime has moved (step B)."""
    doc = copy.deepcopy(FIXTURES[LEGACY_PROBE]["document"])
    doc.pop("recovery_observations", None)
    doc["observations"] = [copy.deepcopy(doc["execution_result"]["observation"])]
    assert "schema_violation" in _contract_codes(doc)  # the contract draft already refuses it
    reports = [r for r in _import_bundle(doc).records if r.record_type == "executor_recovery_report"]
    assert [r.source_path for r in reports] == ["moltbot.observations[0]"]


def test_mixed_layout_is_refused():
    """The legacy mirror together with recovery_observations is neither layout."""
    doc = copy.deepcopy(FIXTURES[LEGACY_PROBE]["document"])
    report = doc["execution_result"]["observation"]
    doc["observations"] = [copy.deepcopy(report)]
    doc["recovery_observations"] = [copy.deepcopy(report)]
    outcome = evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "observations_mismatch"


def test_validated_observation_listed_in_recovery_observations_is_refused():
    doc = copy.deepcopy(FIXTURES["executor-normal-observations-member"]["document"])
    doc["recovery_observations"] = [copy.deepcopy(doc["execution_result"]["observation"])]
    outcome = evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "recovery_observations_mismatch"


@pytest.mark.parametrize("observation", ["validated", "none"])
def test_observed_result_cannot_claim_an_attempt_for_any_observation_kind(observation):
    doc = copy.deepcopy(FIXTURES["observed-result-claims-attempt"]["document"])
    if observation == "none":
        doc["execution_result"]["observation"] = None
        doc["execution_result"]["observed_state"] = "unknown"
    assert "observed_result_claims_attempt" in _contract_codes(doc)
    outcome = evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "observed_result_claims_attempt", outcome.message


@pytest.mark.parametrize("empty", [None, {}])
def test_executed_result_with_a_null_or_empty_observation_is_refused(empty):
    doc = copy.deepcopy(FIXTURES["executed-without-observation"]["document"])
    doc["execution_result"]["observation"] = empty
    outcome = evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "executed_without_observation", outcome.message


def test_empty_observation_object_is_tolerated_as_no_observation():
    """A real producer exports ``observation: {}`` on a denied result (examples/producer-v2/producer_v2_prior_absence.json)
    although the contract allows only null; Replay keeps treating it as no observation (owner decision pending)."""
    doc = copy.deepcopy(FIXTURES["executor-denied-attempt-event"]["document"])
    doc["execution_result"]["observation"] = {}
    assert "schema_violation" in _contract_codes(doc)
    assert evaluate_doc(doc).accepted


def test_denied_is_an_attempt_event_status_and_other_values_are_not():
    doc = copy.deepcopy(FIXTURES["executor-denied-attempt-event"]["document"])
    assert evaluate_doc(doc).accepted
    doc["attempt_events"][1]["status"] = "rejected"
    assert "unknown_enum_value" in _contract_codes(doc)
    outcome = evaluate_doc(doc)
    assert not outcome.accepted and outcome.code == "unknown_enum_value"


def test_unknown_with_a_validated_observation_is_refused_whatever_the_terminal_event():
    doc = copy.deepcopy(FIXTURES["executor-unknown-with-validated-observation"]["document"])
    for terminal in ("executed", "unknown"):
        doc["attempt_events"][1]["status"] = terminal
        outcome = evaluate_doc(doc)
        assert not outcome.accepted and outcome.code == "unknown_with_validated_observation", terminal


@pytest.mark.parametrize("status", ["acknowledged", "partial"])
def test_reconciled_marker_is_valid_on_a_lone_acknowledged_or_partial_row(status):
    doc = copy.deepcopy(FIXTURES[R_CP]["document"])
    doc["control_plane_attempts"][0]["status"] = status
    assert not _contract_codes(doc)
    assert _direct_cp_validator(doc).accepted


@pytest.mark.parametrize("status", ["failed", "unknown", "attempted"])
def test_reconciled_marker_is_refused_on_any_other_status(status):
    doc = copy.deepcopy(FIXTURES[R_CP]["document"])
    doc["control_plane_attempts"][0]["status"] = status
    assert "invalid_reconciled_marker" in _contract_codes(doc)
    outcome = _direct_cp_validator(doc)
    assert not outcome.accepted and outcome.code == "invalid_reconciled_marker"


def test_reconciled_marker_must_be_boolean_true_not_a_truthy_value():
    doc = copy.deepcopy(FIXTURES[R_CP]["document"])
    doc["control_plane_attempts"][0]["acknowledgement"] = {"reconciled_existing": 1}
    assert "invalid_reconciled_marker" in _contract_codes(doc)
    outcome = _direct_cp_validator(doc)
    assert not outcome.accepted and outcome.code == "invalid_reconciled_marker"


def test_started_at_is_immutable_across_control_plane_rows():
    """Refused with the contract code on a repaired revision."""
    cp, proposal, x = load_security()
    cp["attempts"][1]["started_at"] = "2026-10-05T19:00:09+00:00"
    outcome = run_import(cp, proposal, x)
    assert not outcome.accepted and outcome.code == "attempt_started_at_changed"


def test_started_at_immutability_is_coded_on_the_legacy_revision_too():
    """The legacy revision skips the repaired-run validator; the importer's own invariant check carries the code."""
    from tests.test_importers import bounded_source
    cp = bounded_source()
    cp["attempts"][1]["started_at"] = "2026-10-05T00:00:09Z"
    with pytest.raises(ImportContractError, match="conflicting content under immutable attempt_id") as info:
        import_bounded_workflow(cp)
    assert info.value.code == "attempt_started_at_changed"


@pytest.mark.parametrize("name", ["x-Upper", "x-", "x_trace", "trace", "x- space"])
def test_extension_names_follow_the_contract_pattern(name):
    cp, proposal, x = load_security()
    x["extensions"] = {name: 1}
    outcome = run_import(cp, proposal, x)
    assert not outcome.accepted and outcome.code == "invalid_extension_key"


def test_members_the_contract_leaves_optional_are_not_required():
    """RP-11: observations, recovery_observations, control_plane_attempts, and the optional row and result members."""
    cp, proposal, x = load_security()
    for name in ("observations", "control_plane_attempts"):
        x.pop(name)
    x["execution_result"].pop("decision_id")
    x["execution_result"].pop("effect_id")
    x["execution_result"].pop("error")
    x["attempts"][0].pop("operation_digest")
    x["attempts"][0].pop("created_at")
    x["attempt_events"][0].pop("error")
    assert run_import(cp, proposal, x).accepted


@pytest.mark.parametrize("member", ["status", "attempt_id", "observed_state", "observation"])
def test_members_the_contract_requires_are_still_required(member):
    cp, proposal, x = load_security()
    x["execution_result"].pop(member)
    outcome = run_import(cp, proposal, x)
    assert not outcome.accepted and outcome.code == "schema_violation", outcome.message


@pytest.mark.parametrize("path", [("attempts", 0, "effect_id"), ("attempt_events", 0, "created_at"),
                                  ("attempt_events", 0, "event_id")])
def test_required_row_members_are_still_required(path):
    cp, proposal, x = load_security()
    x[path[0]][path[1]].pop(path[2])
    outcome = run_import(cp, proposal, x)
    assert not outcome.accepted and outcome.code == "schema_violation", outcome.message


def test_captured_exports_satisfy_the_new_result_rules():
    """No real captured export in tests/fixtures says result 'observed' with an attempt, or 'executed' without an
    observation, so the new rules need no change to a captured fixture."""
    seen = 0
    for path in sorted(BASES.rglob("executor.json")):
        result = json.loads(path.read_text(encoding="utf-8"))["execution_result"]
        seen += 1
        if result["status"] == "observed":
            assert not result["attempted"] and result["attempt_id"] is None, path
        if result["status"] == "executed":
            assert result["observation"], path
    assert seen == 4


# ---------------------------------------------------------------------------------------------------------
# Generated tables (kept verbatim in the doc)
# ---------------------------------------------------------------------------------------------------------

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _cell(text: str) -> str:
    text = _UUID.sub("<id>", text).replace("|", "/").replace("\n", " ")
    return text if len(text) <= 150 else text[:147] + "..."


def _refusal_cell(outcome) -> str:
    return f"`{outcome.code}`: {outcome.message}" if outcome.code else outcome.message


def render_fixture_table() -> str:
    lines = ["| Fixture | Contract expects | Status | Replay does | Note |", "|---|---|---|---|---|"]
    for fid, fixture in FIXTURES.items():
        status, outcome = classify(fixture)
        expects = "accept" if fixture["expected_outcome"] == "accept" else "refuse: " + fixture["expected_refusal"]
        if status == "NOT-EXERCISED":
            does, note = "not run", NOT_EXERCISED[fid]
        else:
            does = "accepted" if outcome.accepted else _refusal_cell(outcome)
            note = NOTES.get(fid, "")
        lines.append(f"| `{fid}` | {expects} | {status} | {_cell(does)} | {_cell(note)} |")
    return "\n".join(lines)


def render_probe_table() -> str:
    lines = ["| Probe | Contract (vendored validator) | Status | Replay does | Finding |", "|---|---|---|---|---|"]
    for probe in PROBES:
        outcome = probe.get("runner", evaluate_doc)(_probe_doc(probe))
        expects = "valid" if probe["code"] is None else probe["code"]
        does = "accepted" if outcome.accepted else _refusal_cell(outcome)
        lines.append(f"| `{probe['id']}` | {expects} | {_probe_status(probe)} | {_cell(does)} | {probe['finding'] or ''} |")
    return "\n".join(lines)


def render_mapping_table() -> str:
    lines = ["| Contract code | Replay message pattern | Emitted by Replay | Note |", "|---|---|---|---|"]
    for code in sorted(CODE_TO_REPLAY):
        mapped = CODE_TO_REPLAY[code]
        emitted = "no" if code in NOT_EMITTED else "yes"
        note = NOT_EMITTED.get(code) or mapped.note
        lines.append(f"| `{code}` | `{mapped.pattern.replace('|', chr(92) + '|')}` | {emitted} | {note} |")
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
