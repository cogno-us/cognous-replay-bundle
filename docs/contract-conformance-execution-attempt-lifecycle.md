# Contract conformance: execution-attempt-lifecycle (consumer)

Replay is the consumer of the ODES `execution-attempt-lifecycle` contract (ODES issue
cogno-us/cognous-control-plane#38, steps P2 and P3; P3b applies the owner decisions of the second batch, ODES decision-log items 13 to 17).

| | |
|---|---|
| Contract | `execution-attempt-lifecycle` `0.1.0-draft` (draft, not frozen; any change may break) |
| Vendored from | `cogno-us/open-decision-evidence-standard` at `a9db024c6f346f741a9963552e559476fdfc4189`, in `tests/contracts/execution-attempt-lifecycle/` (`CONTRACT.json` lists the SHA-256 of every file) |
| Role | consumer |
| Level claimed | `L` (structure and lifecycle rules) for every vendored fixture except the four DIVERGES below (all deliberate step A tolerances). Closed member sets and closed enumerations are enforced for the executor attempt rows, attempt events, result, recovery report, validated observation state and Control Plane attempt rows of a producer 2.0.0 export; the resolution journal events, journal inputs, resolution checks and check inputs are closed pydantic models that accept and preserve `x-` extensions. |
| Test | `tests/test_contract_lifecycle_conformance.py`; the importer changes are in `src/agent_replay_bundle/importers.py` and `refusal_evidence.py` (P3 and P3b) |

## How it is tested

The vendored fixtures are abstract (synthetic ids). Each fixture family has an adapter that builds the minimum real
Replay input and calls the real code through `import_bounded_workflow`:

- executor rows and result: planted over the real captured exports in `tests/fixtures/route_b_post_commit/`
  (recovery reports) and `tests/fixtures/security_runtime_valid/` (validated observations), with the real Control Plane run;
- `control_plane_attempts`: replace `attempts` of the real run (`_validate_repaired_run`);
- `resolution_journal` / `resolution_checks`: replace `check_events` / `resolution_checks` (`refusal_evidence.validate_run`).

Completions are limited to what Replay needs and the contract leaves abstract: synthetic ids and the synthetic
observation time are rebound to the capture's, the attempt row takes the capture's `operation_digest` / `created_at`,
a validated applied observation takes the capture's `destination_state` when the fixture has none or `{}`, and for a
denied result the capture's effect and Control Plane attempt evidence is cleared. `observations` is not mirrored
(the contract leaves it optional and Replay accepts its absence).
Every REFUSED fixture has a control: the same adapter accepts it once only the planted defect is repaired.
Replay refuses with the contract's code (`ImportContractError.code`), so a refusal counts only with the expected code
and a message matching the pattern in the mapping table. A DIVERGES fixture is a strict xfail that states the contract
expectation; a NOT-EXERCISED fixture is a test that asserts the stated reason.

## Fixtures

<!-- BEGIN FIXTURE TABLE -->
| Fixture | Contract expects | Status | Replay does | Note |
|---|---|---|---|---|
| `control-plane-attempt-extensions-preserved` | accept | ACCEPTED | accepted |  |
| `control-plane-normal-attempted-acknowledged` | accept | ACCEPTED | accepted |  |
| `control-plane-reconciled-existing-acknowledged` | accept | ACCEPTED | accepted |  |
| `control-plane-reconciled-existing-partial` | accept | ACCEPTED | accepted |  |
| `executor-denied-attempt-event` | accept | ACCEPTED | accepted | adapter clears the capture's effect and Control Plane attempt evidence (nothing was attempted) |
| `executor-normal-attempted-executed-observed` | accept | ACCEPTED | accepted |  |
| `executor-normal-observations-member` | accept | ACCEPTED | accepted |  |
| `executor-observed-effect-free-reconcile-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-ack-unobserved` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-hold-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-observation-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-separate-member-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-unavailable-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-validated-absent-after-ambiguous-dispatch` | accept | ACCEPTED | accepted |  |
| `executor-unknown-validated-unknown-after-ambiguous-dispatch` | accept | ACCEPTED | accepted | adapter: the reconciliation accepts the validated unknown reading (result hold, no destination content); Replay now accepts a validated unknown sta... |
| `extension-namespace-member-preserved` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-a-completes-first` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-completion-order` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-open-order` | accept | ACCEPTED | accepted |  |
| `resolution-journal-checks-extensions-preserved` | accept | ACCEPTED | accepted |  |
| `attempt-started-at-changed` | refuse: attempt_started_at_changed | REFUSED | `attempt_started_at_changed`: Control Plane attempt <id> started_at changed between lifecycle rows |  |
| `control-plane-attempt-extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: attempts[0].extensions names must start with 'x-': trace |  |
| `control-plane-attempt-undeclared-member` | refuse: undeclared_member | REFUSED | `undeclared_member`: attempts[0] has unsupported member(s): injected_member |  |
| `control-plane-dropped-start-record` | refuse: missing_start_record | REFUSED | `missing_start_record`: Control Plane attempt <id> lifecycle lacks its attempted start record |  |
| `control-plane-start-row-reconciled-existing-false` | refuse: invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt <id> carries an invalid reconciled_existing marker |  |
| `effect-free-reconcile-claims-attempt` | refuse: effect_free_reconcile_claims_attempt | REFUSED | `effect_free_reconcile_claims_attempt`: an effect-free reconcile result cannot claim an attempt, acknowledgement or new effect |  |
| `effect-free-reconcile-state-mismatch` | refuse: recovery_state_mismatch | REFUSED | `recovery_state_mismatch`: recovery report observed-state contradiction |  |
| `empty-object-observation` | refuse: schema_violation | DIVERGES | accepted | deliberate step A: observation {} is still tolerated as no observation (a real producer exports it on a denied result); step B refuses it (schema_v... |
| `executed-without-observation` | refuse: executed_without_observation | REFUSED | `executed_without_observation`: an executed result must carry the observation that established it |  |
| `executor-dropped-start-event` | refuse: missing_start_event | REFUSED | `missing_start_event`: executor attempt <id> events do not start with attempted |  |
| `executor-dropped-terminal-event` | refuse: terminal_event_missing | REFUSED | `terminal_event_missing`: execution result status 'executed' contradicts the terminal attempt event 'attempted' |  |
| `executor-terminal-failed-vs-status` | refuse: status_terminal_mismatch | REFUSED | `status_terminal_mismatch`: execution result status 'executed' contradicts the terminal attempt event 'failed' |  |
| `executor-unknown-recovery-state-contradiction` | refuse: unknown_state_mismatch | REFUSED | `unknown_state_mismatch`: recovery report observed-state contradiction |  |
| `executor-unknown-validated-absent-state-mismatch` | refuse: unknown_state_mismatch | REFUSED | `unknown_state_mismatch`: unknown result observed-state contradiction with its validated observation |  |
| `executor-unknown-with-validated-observation` | refuse: unknown_with_validated_observation | DIVERGES | accepted | narrowed RP-6, applied/partial refusal deferred to step B (owner decision 2026-10-17): the pinned runtimes still export a lost ack as unknown with ... |
| `executor-unknown-with-validated-partial-observation` | refuse: unknown_with_validated_observation | DIVERGES | accepted | same as executor-unknown-with-validated-observation (validated partial on result unknown): refusal behind ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATIO... |
| `extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: moltbot_export.extensions names must start with 'x-': trace | rule order: refused here before observed_result_claims_attempt would be |
| `mixed-layout-observations-disagree-with-result` | refuse: observations_mismatch | REFUSED | `observations_mismatch`: accepted executor observations differ from result |  |
| `null-observation-state-absent` | refuse: null_observation_state_mismatch | REFUSED | `null_observation_state_mismatch`: null observation cannot establish observed state |  |
| `null-observation-state-applied-failed-result` | refuse: null_observation_state_mismatch | REFUSED | `null_observation_state_mismatch`: null observation cannot establish observed state |  |
| `observed-result-claims-attempt` | refuse: observed_result_claims_attempt | REFUSED | `observed_result_claims_attempt`: an observed result cannot claim an attempt, acknowledgement or new effect (a normal execution reports executed) |  |
| `recovery-applied-missing-operation-digest` | refuse: recovery_report_incomplete | REFUSED | `recovery_report_incomplete`: execution_result.observation.operation_digest is required for an applied recovery report |  |
| `recovery-hold-missing-reason` | refuse: recovery_report_incomplete | REFUSED | `recovery_report_incomplete`: execution_result.observation.reason is required for a hold recovery report |  |
| `recovery-observations-differs-from-result` | refuse: recovery_observations_mismatch | REFUSED | `recovery_observations_mismatch`: recovery_observations differ from the result report |  |
| `recovery-report-in-observations-member` | refuse: schema_violation | DIVERGES | accepted | deliberate step A: the legacy layout (report mirrored in observations) is still tolerated until step B (owner decision 1); the contract draft alrea... |
| `recovery-retry-eligible-true` | refuse: recovery_retry_eligible | REFUSED | `recovery_retry_eligible`: unsupported retry eligibility |  |
| `resolution-check-undeclared-member` | refuse: undeclared_member | REFUSED | `undeclared_member`: typed refusal profile: unsupported/missing evidence fields |  |
| `resolution-checks-sequential-reorder` | refuse: resolution_checks_out_of_order | REFUSED | `resolution_checks_out_of_order`: typed refusal profile: resolution checks are out of journal order |  |
| `resolution-journal-extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: typed refusal profile: check_events.extensions names must start with 'x-': note |  |
| `result-status-unknown-enum-value` | refuse: unknown_enum_value | REFUSED | `unknown_enum_value`: execution_result.status is not a declared value: 'finished' |  |
| `undeclared-member-outside-extensions` | refuse: undeclared_member | REFUSED | `undeclared_member`: execution_result has unsupported member(s): injected_member | rule order: refused here before observed_result_claims_attempt would be |
<!-- END FIXTURE TABLE -->

Totals: 20 ACCEPTED, 27 REFUSED, 4 DIVERGES, 0 NOT-EXERCISED.

## Probes beyond the fixtures

Each probe is first checked against the vendored reference validator, then run through Replay.

<!-- BEGIN PROBE TABLE -->
| Probe | Contract (vendored validator) | Status | Replay does | Finding |
|---|---|---|---|---|
| `undeclared-member-attempt-row` | undeclared_member | REFUSED | `undeclared_member`: moltbot.attempts[0] has unsupported member(s): injected |  |
| `undeclared-member-event-row` | undeclared_member | REFUSED | `undeclared_member`: moltbot.attempt_events[1] has unsupported member(s): injected |  |
| `undeclared-member-control-plane-attempt-row` | undeclared_member | REFUSED | `undeclared_member`: attempts[0] has unsupported member(s): injected |  |
| `undeclared-member-recovery-report` | undeclared_member | REFUSED | `undeclared_member`: execution_result.observation recovery report has undeclared members: injected |  |
| `extension-bad-key-attempt-row` | invalid_extension_key | REFUSED | `invalid_extension_key`: moltbot.attempts[0].extensions names must start with 'x-': trace |  |
| `extension-bad-key-result` | invalid_extension_key | REFUSED | `invalid_extension_key`: execution_result.extensions names must start with 'x-': trace |  |
| `reconciled-marker-extra-acknowledgement-member` | invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `reconciled-marker-non-boolean` | invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `reconciled-marker-on-failed-row` | invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `reconciled-marker-on-unknown-row` | invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `enum-result-and-terminal-event-status` | unknown_enum_value | REFUSED | `unknown_enum_value`: moltbot.attempt_events[1].status is not a declared value: 'finished' |  |
| `enum-middle-event-status` | unknown_enum_value | REFUSED | `unknown_enum_value`: moltbot.attempt_events[1].status is not a declared value: 'bogus' |  |
| `enum-control-plane-attempt-status` | unknown_enum_value | REFUSED | `unknown_enum_value`: attempts[1].status is not a declared value: 'bogus' |  |
| `enum-control-plane-time-source` | unknown_enum_value | REFUSED | `unknown_enum_value`: attempts[1].time_source is not a declared value: 'bogus' |  |
| `enum-recovery-status` | unknown_enum_value | REFUSED | `unknown_enum_value`: execution_result.observation.status is not a recovery status |  |
| `enum-validated-observation-state` | unknown_enum_value | REFUSED | `unknown_enum_value`: execution_result.observation.state is not a declared value: 'bogus' |  |
| `recovery-report-on-executed-result` | recovery_observation_status | REFUSED | `recovery_observation_status`: a recovery report is only carried by results unknown or observed |  |
| `executed-result-with-null-observation` | executed_without_observation | REFUSED | `executed_without_observation`: an executed result must carry the observation that established it |  |
| `export-without-observations-member` | valid | ACCEPTED | accepted |  |
<!-- END PROBE TABLE -->

## Mapping from contract code to Replay message

<!-- BEGIN MAPPING TABLE -->
| Contract code | Replay message pattern | Emitted by Replay | Note |
|---|---|---|---|
| `attempt_started_at_changed` | `started_at changed between lifecycle rows\|conflicting content under immutable attempt_id` | yes |  |
| `attempt_without_events` | `executor attempt .* has no attempt events` | yes |  |
| `duplicate_attempt_row` | `duplicate executor attempt row` | yes |  |
| `duplicate_check_id` | `duplicate/empty resolution check id` | yes |  |
| `effect_free_reconcile_claims_attempt` | `an effect-free reconcile result cannot claim an attempt` | yes |  |
| `event_order` | `attempt_events\[\d+\] (event_id is repeated or out of order\|created_at is missing or out of order)` | yes |  |
| `executed_without_observation` | `an executed result must carry the observation` | yes |  |
| `invalid_extension_key` | `extensions names must start with 'x-'` | yes |  |
| `invalid_reconciled_marker` | `invalid reconciled_existing marker` | yes |  |
| `journal_check_reused` | `completed journals reuse one actual resolution check` | yes |  |
| `journal_protocol` | `journal (missing opening or already closed\|binding changed\|input missing)\|duplicate journal opening` | yes |  |
| `journal_unbound_completion` | `completed journal differs from actual resolution check` | yes |  |
| `missing_start_event` | `executor attempt .* events do not start with attempted` | yes |  |
| `missing_start_record` | `lifecycle lacks its attempted start record` | yes |  |
| `null_observation_state_mismatch` | `null observation cannot establish observed state` | yes |  |
| `observations_mismatch` | `accepted executor observations differ from result` | yes |  |
| `observed_result_claims_attempt` | `an observed result cannot claim an attempt` | yes |  |
| `recovery_observation_status` | `a recovery report is only carried by results unknown or observed` | yes |  |
| `recovery_observations_mismatch` | `recovery_observations differ from the result report` | yes |  |
| `recovery_report_incomplete` | `(operation_digest\|claim_state\|effect_id\|reason) is required for an? \w+ recovery report` | yes |  |
| `recovery_retry_eligible` | `unsupported retry eligibility` | yes |  |
| `recovery_state_mismatch` | `recovery report observed-state contradiction` | yes |  |
| `repeated_record` | `lifecycle repeats a record` | yes |  |
| `repeated_start_event` | `executor attempt .* repeats its attempted event` | yes |  |
| `resolution_checks_out_of_order` | `resolution checks are out of journal order` | yes |  |
| `schema_violation` | `is required\|must be an (object\|array)\|must be object or null` | yes | Replay's legacy-layout tolerance means the contract's own schema_violation fixture is accepted (see the DIVERGES note); Replay emits this code for structural failures |
| `status_terminal_mismatch` | `execution result status .* contradicts the terminal attempt event` | yes |  |
| `terminal_event_missing` | `execution result status .* contradicts the terminal attempt event 'attempted'` | yes |  |
| `undeclared_member` | `has unsupported member\(s\)\|recovery report has undeclared members\|unsupported/missing evidence fields` | yes |  |
| `unknown_enum_value` | `is not a recovery status\|is not a declared value` | yes |  |
| `unknown_state_mismatch` | `recovery report observed-state contradiction\|unknown result observed-state contradiction` | yes |  |
| `unknown_with_validated_observation` | `unknown result cannot carry a validated observation` | yes |  |
| `unsupported_contract_version` | `contract_version` | no | Replay exports carry no contract_version member |
<!-- END MAPPING TABLE -->

## Findings

P2 recorded findings F-P2-RP-1 to F-P2-RP-12. The P3 alignment (owner decisions of 2026-10-17) resolved all of them
except the one decision below. Evidence for the current behaviour is the tests, not line numbers.

| Finding | Resolution |
|---|---|
| RP-1 `observed` with `attempted` true | The contract now says a normal execution reports `executed`; result `observed` cannot claim an attempt for any observation kind (`observed_result_claims_attempt`; recovery reports keep `effect_free_reconcile_claims_attempt`). No real captured export conflicts. |
| RP-2 `started_at` immutable | The contract adopted it (`attempt_started_at_changed`). |
| RP-3, RP-4 `recovery_observations`, layout | Accepted: `observations` lists the validated observation only, `recovery_observations` is optional, `execution_result.observation` carries the report. Mismatches are `observations_mismatch` / `recovery_observations_mismatch`. |
| RP-5 legacy layout | Deliberately still tolerated (step A, owner item 17: a recovery report inside `observations` stays tolerated until step B): a report mirrored in `observations`, with no `recovery_observations`, is accepted and retained as `executor_recovery_report`. The fixture `recovery-report-in-observations-member` therefore stays a strict xfail until step B drops the legacy layout. The mixed layout (the mirror together with `recovery_observations`, or a validated observation the result does not carry) is refused today as `observations_mismatch` (fixture `mixed-layout-observations-disagree-with-result`). |
| RP-6 unknown with a validated observation (narrowed, owner item 14) | Result `unknown` may carry a validated observation whose state is `absent` or `unknown`, with `observed_state` equal to `observation.state` (`unknown_state_mismatch` otherwise): accepted now. The refusal of `unknown` with a validated `applied`/`partial` observation (`unknown_with_validated_observation`, whatever the terminal event) is written but NOT enforced yet: the pinned runtimes still export a lost ack as `unknown` with a validated `applied` observation until the pins advance in P4, so it stays behind `ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATION` (False); the fixtures `executor-unknown-with-validated-observation` and `executor-unknown-with-validated-partial-observation` are strict xfails until step B. To carry a validated `unknown` reading Replay now accepts state `unknown` (empty destination state, reconciliation result `hold`) as an accepted Control Plane observation. |
| RP-7 closed enumerations | Enforced (`unknown_enum_value`) for result, event and Control Plane attempt statuses, `time_source` and the validated observation state; `denied` is a valid event status. |
| RP-8 closed members, `x-` keys | Enforced for attempt rows, events and Control Plane attempt rows as well (`undeclared_member`, `invalid_extension_key`); the extension name pattern is the contract's. P3b (owner item 16): `x-` extensions are accepted and preserved verbatim on resolution journal events and inputs, resolution checks and check inputs (the journal-to-check content binding ignores `extensions`), and on Control Plane attempt rows (closed sets, extras only via `extensions`). |
| RP-9 reconciled marker | Valid only as the whole acknowledgement of a lone `acknowledged`/`partial` row, and exactly `true`. |
| RP-10 `executed` without observation | Refused (`executed_without_observation`). |
| RP-11 optional members | `observations`, `recovery_observations`, `control_plane_attempts`, result `decision_id`/`effect_id`, attempt `operation_digest` are no longer required; members the contract requires still are (`schema_violation`). |
| RP-12 export-level `extensions` | Retained as the record `executor_export_extensions`. |

Replay behaviour that goes beyond or differs from the contract, kept on purpose (step A):

- `execution_result.observation: {}` (a real producer exports it on a denied result, `examples/producer-v2/producer_v2_prior_absence.json`) is still tolerated as no observation. The contract allows only null (owner item 13). Step B refuses it with `schema_violation`; the fixture `empty-object-observation` is a strict xfail until then.
- A recovery report inside `observations` (legacy layout) is still tolerated (see RP-5).
- `unknown` with a validated `applied`/`partial` observation is still tolerated (see RP-6).

Replay now matches the contract on the null-observation rule (owner item 15, reversing the P3 relaxation): whenever the observation is null, `observed_state` is `unknown` for every result status (`null_observation_state_mismatch`). This is also what real denied exports carry.

## Refreshing the vendored copy

```
git -C open-decision-evidence-standard checkout <commit>
python open-decision-evidence-standard/contracts/tools/vendor_contract.py copy \
  --contract execution-attempt-lifecycle \
  --dest tests/contracts/execution-attempt-lifecycle \
  --role consumer --level L --odes-commit <commit>
```

`python open-decision-evidence-standard/contracts/tools/vendor_contract.py check --dest tests/contracts/execution-attempt-lifecycle`
verifies the copy against its `CONTRACT.json`.

Then set `ODES_COMMIT` in the test, run `PYTHONPATH=.:src python -m pytest -q tests`, regenerate the tables with
`PYTHONPATH=src python -m tests.test_contract_lifecycle_conformance`, paste them between the markers above, and update
`DECLARED`, `NOTES` and `NOT_EXERCISED` in the test for every fixture whose status changed. Never edit the vendored files by hand:
the drift test fails on a modified, missing or unlisted file.
