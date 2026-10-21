# Contract conformance: execution-attempt-lifecycle (consumer)

Replay is the consumer of the ODES `execution-attempt-lifecycle` contract (ODES issue
cogno-us/cognous-control-plane#38, steps P2 and P3; P3b applies the owner decisions of the second batch, ODES decision-log items 13 to 17).

| | |
|---|---|
| Contract | `execution-attempt-lifecycle` `0.1.0-draft` (draft, not frozen; any change may break) |
| Vendored from | `cogno-us/open-decision-evidence-standard` at `59ca4c797b4c0700b581815a53b113a60bda1c67`, in `tests/contracts/execution-attempt-lifecycle/` (`CONTRACT.json` lists the SHA-256 of every file) |
| Role | consumer |
| Level claimed | `L` (structure and lifecycle rules) for every vendored fixture except the three DIVERGES below (a validated `unknown` observation on result `unknown`, which waits for a Control Plane that emits it, and the two invalid fixtures that carry it), and for two documented probe DIVERGES (`reasons_minimum` and the closed post-journal reason set, see Findings). Closed member sets and closed enumerations are enforced for the executor attempt rows, attempt events, result, recovery report, validated observation state and Control Plane attempt rows of a producer 2.0.0 export; the resolution journal events, journal inputs, resolution checks and check inputs are closed pydantic models that accept and preserve `x-` extensions. |
| Test | `tests/test_contract_lifecycle_conformance.py`; the importer changes are in `src/agent_replay_bundle/importers.py` and `refusal_evidence.py` (P3 and P3b) |

## How it is tested

The vendored fixtures are abstract (synthetic ids). Each fixture family has an adapter that builds the minimum real
Replay input and calls the real code through `import_bounded_workflow`:

- executor rows and result: planted over the real captured exports in `tests/fixtures/route_b_post_commit/`
  (recovery reports) and `tests/fixtures/security_runtime_valid/` (validated observations), with the real Control Plane run;
- `control_plane_attempts`: replace `attempts` of the real run (`_validate_repaired_run`);
- `resolution_journal` / `resolution_checks`: replace `check_events` / `resolution_checks` (`refusal_evidence.validate_run`).

A document that carries several families (`journal-refusal-then-valid-request`: attempts, journal and checks of one run) is
imported as one run. Ids taken from a real run (not `syn-`) are rebound onto the base capture's single decision and effect.
Text that is not valid Unicode has no counterpart for a document-level label such as `producer`, so the adapter carries it
into an `x-` extension member of the real input (documents with valid text are imported unchanged).

Completions are limited to what Replay needs and the contract leaves abstract: synthetic ids and the synthetic
observation time are rebound to the capture's, the attempt row takes the capture's `operation_digest` / `created_at`,
a validated applied observation takes the capture's `destination_state` when the fixture has none or `{}`, an observed absence gets `destination_state` `{}`, and for a
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
| `executor-denied-attempt-event` | accept | ACCEPTED | accepted |  |
| `executor-normal-attempted-executed-observed` | accept | ACCEPTED | accepted |  |
| `executor-normal-observations-member` | accept | ACCEPTED | accepted |  |
| `executor-observed-effect-free-reconcile-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-ack-unobserved` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-hold-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-observation-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-separate-member-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-unavailable-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-validated-absent-after-ambiguous-dispatch` | accept | ACCEPTED | accepted |  |
| `executor-unknown-validated-unknown-after-ambiguous-dispatch` | accept | DIVERGES | unsupported accepted observation state | waits until the Control Plane emits an `unknown` observation; owner decision 2026-10-17 not to widen CP acceptance unreviewed |
| `extension-namespace-member-preserved` | accept | ACCEPTED | accepted |  |
| `journal-refusal-then-valid-request` | accept | ACCEPTED | accepted | adapter: the document's decision and effect ids (a real run) are rebound onto the base capture's single decision and effect; the journal, checks an... |
| `resolution-checks-overlap-a-completes-first` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-completion-order` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-open-order` | accept | ACCEPTED | accepted |  |
| `resolution-journal-checks-extensions-preserved` | accept | ACCEPTED | accepted |  |
| `attempt-started-at-changed` | refuse: attempt_started_at_changed | REFUSED | `attempt_started_at_changed`: Control Plane attempt <id> started_at changed between lifecycle rows |  |
| `control-plane-attempt-extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: attempts[0].extensions names must start with 'x-': trace |  |
| `control-plane-attempt-identity-changed` | refuse: attempt_identity_changed | REFUSED | `attempt_identity_changed`: Control Plane attempt <id> changed its effect_id or decision_id between lifecycle rows |  |
| `control-plane-attempt-undeclared-member` | refuse: undeclared_member | REFUSED | `undeclared_member`: attempts[0] has unsupported member(s): injected_member |  |
| `control-plane-dropped-start-record` | refuse: missing_start_record | REFUSED | `missing_start_record`: Control Plane attempt <id> lifecycle lacks its attempted start record |  |
| `control-plane-empty-attempts-ghost-result` | refuse: result_attempt_unresolved | DIVERGES | Moltbot export missing: attempt_events,attempts | refused, but before the contract's rule runs: the export import requires the `attempts` and `attempt_events` members (`Moltbot export missing: ...`... |
| `control-plane-failed-after-acknowledged` | refuse: attempt_transition | REFUSED | `attempt_transition`: conflicting content under immutable terminal Control Plane attempt <id> |  |
| `control-plane-start-row-reconciled-existing-false` | refuse: invalid_reconciled_marker | REFUSED | `invalid_reconciled_marker`: Control Plane attempt <id> carries an invalid reconciled_existing marker |  |
| `effect-free-reconcile-claims-attempt` | refuse: effect_free_reconcile_claims_attempt | REFUSED | `effect_free_reconcile_claims_attempt`: an effect-free reconcile result cannot claim an attempt, acknowledgement or new effect |  |
| `effect-free-reconcile-state-mismatch` | refuse: recovery_state_mismatch | REFUSED | `recovery_state_mismatch`: recovery report observed-state contradiction |  |
| `empty-object-observation` | refuse: schema_violation | REFUSED | `schema_violation`: execution observation must be null or a typed observation, not {} |  |
| `executed-without-observation` | refuse: executed_without_observation | REFUSED | `executed_without_observation`: an executed result must carry the observation that established it |  |
| `executor-dropped-start-event` | refuse: missing_start_event | REFUSED | `missing_start_event`: executor attempt <id> events do not start with attempted |  |
| `executor-dropped-terminal-event` | refuse: terminal_event_missing | REFUSED | `terminal_event_missing`: execution result status 'executed' contradicts the terminal attempt event 'attempted' |  |
| `executor-events-out-of-order-without-attempts-member` | refuse: event_order | DIVERGES | Moltbot export missing: attempts | refused, but before the contract's rule runs: the export import requires the `attempts` and `attempt_events` members (`Moltbot export missing: ...`... |
| `executor-failed-after-executed` | refuse: attempt_transition | REFUSED | `attempt_transition`: executor attempt <id> event 'failed' may not follow 'executed' |  |
| `executor-failed-attempt-reopened` | refuse: attempt_transition | REFUSED | `attempt_transition`: executor attempt <id> event 'executed' may not follow 'failed' |  |
| `executor-ghost-result-without-attempts-member` | refuse: result_attempt_unresolved | DIVERGES | Moltbot export missing: attempt_events,attempts | refused, but before the contract's rule runs: the export import requires the `attempts` and `attempt_events` members (`Moltbot export missing: ...`... |
| `executor-terminal-failed-vs-status` | refuse: status_terminal_mismatch | REFUSED | `status_terminal_mismatch`: execution result status 'executed' contradicts the terminal attempt event 'failed' |  |
| `executor-unknown-recovery-state-contradiction` | refuse: unknown_state_mismatch | REFUSED | `unknown_state_mismatch`: recovery report observed-state contradiction |  |
| `executor-unknown-validated-absent-state-mismatch` | refuse: unknown_state_mismatch | REFUSED | `unknown_state_mismatch`: unknown result observed-state contradiction with its validated observation |  |
| `executor-unknown-with-validated-observation` | refuse: unknown_with_validated_observation | REFUSED | `unknown_with_validated_observation`: an unknown result cannot carry a validated applied/partial observation |  |
| `executor-unknown-with-validated-partial-observation` | refuse: unknown_with_validated_observation | REFUSED | `unknown_with_validated_observation`: an unknown result cannot carry a validated applied/partial observation |  |
| `extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: moltbot_export.extensions names must start with 'x-': trace |  |
| `mixed-layout-observations-disagree-with-result` | refuse: observations_mismatch | REFUSED | `observations_mismatch`: accepted executor observations differ from result |  |
| `null-observation-state-absent` | refuse: null_observation_state_mismatch | REFUSED | `null_observation_state_mismatch`: null observation cannot establish observed state |  |
| `null-observation-state-applied-failed-result` | refuse: null_observation_state_mismatch | REFUSED | `null_observation_state_mismatch`: null observation cannot establish observed state |  |
| `observation-names-different-effect` | refuse: result_binding_mismatch | REFUSED | `result_binding_mismatch`: execution_result.observation.effect_id conflicts with committed operation |  |
| `observed-result-claims-attempt` | refuse: observed_result_claims_attempt | REFUSED | `observed_result_claims_attempt`: an observed result cannot claim an attempt, acknowledgement or new effect (a normal execution reports executed) |  |
| `recovery-applied-missing-operation-digest` | refuse: recovery_report_incomplete | REFUSED | `recovery_report_incomplete`: execution_result.observation.operation_digest is required for an applied recovery report |  |
| `recovery-hold-missing-reason` | refuse: recovery_report_incomplete | REFUSED | `recovery_report_incomplete`: execution_result.observation.reason is required for a hold recovery report |  |
| `recovery-observations-differs-from-result` | refuse: recovery_observations_mismatch | REFUSED | `recovery_observations_mismatch`: recovery_observations differ from the result report |  |
| `recovery-report-in-observations-member` | refuse: schema_violation | REFUSED | `schema_violation`: moltbot.observations[0] is not a validated observation (it has no state) |  |
| `recovery-retry-eligible-true` | refuse: recovery_retry_eligible | REFUSED | `recovery_retry_eligible`: unsupported retry eligibility |  |
| `resolution-check-undeclared-member` | refuse: undeclared_member | REFUSED | `undeclared_member`: typed refusal profile: unsupported/missing evidence fields |  |
| `resolution-checks-sequential-reorder` | refuse: resolution_checks_out_of_order | REFUSED | `resolution_checks_out_of_order`: typed refusal profile: resolution checks are out of journal order |  |
| `resolution-journal-extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | `invalid_extension_key`: typed refusal profile: check_events.extensions names must start with 'x-': note |  |
| `result-executed-null-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'executed' names no attempt row of the export (a null attempt_id or an id that matches no row ... |  |
| `result-executed-unregistered-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'executed' names no attempt row of the export (a null attempt_id or an id that matches no row ... |  |
| `result-failed-null-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'failed' names no attempt row of the export (a null attempt_id or an id that matches no row is... |  |
| `result-failed-unregistered-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'failed' names no attempt row of the export (a null attempt_id or an id that matches no row is... |  |
| `result-names-different-decision` | refuse: result_binding_mismatch | REFUSED | `result_binding_mismatch`: Moltbot execution_result identifiers do not match execution envelope |  |
| `result-names-different-effect` | refuse: result_binding_mismatch | REFUSED | `result_binding_mismatch`: Moltbot execution_result identifiers do not match execution envelope |  |
| `result-partial-flags-contradict-without-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'partial' names no attempt row of the export (a null attempt_id or an id that matches no row i... |  |
| `result-partial-null-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'partial' names no attempt row of the export (a null attempt_id or an id that matches no row i... |  |
| `result-partial-unregistered-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'partial' names no attempt row of the export (a null attempt_id or an id that matches no row i... |  |
| `result-reconciled-flags-contradict-without-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'reconciled' names no attempt row of the export (a null attempt_id or an id that matches no ro... |  |
| `result-reconciled-null-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'reconciled' names no attempt row of the export (a null attempt_id or an id that matches no ro... |  |
| `result-reconciled-unregistered-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'reconciled' names no attempt row of the export (a null attempt_id or an id that matches no ro... |  |
| `result-state-matrix-executed-not-fresh` | refuse: result_state_matrix | REFUSED | `result_state_matrix`: the producer status matrix contradicts the execution result: an executed result is acknowledged, fresh and observed as applied |  |
| `result-status-unknown-enum-value` | refuse: unknown_enum_value | REFUSED | `unknown_enum_value`: execution_result.status is not a declared value: 'finished' |  |
| `result-unknown-flags-contradict-without-attempt-id` | refuse: result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'unknown' names no attempt row of the export (a null attempt_id or an id that matches no row i... |  |
| `result-unknown-null-attempt-id` | refuse: result_attempt_unresolved | DIVERGES | unsupported accepted observation state | refused (fail closed) at the Control Plane run before the result is read: the fixture's validated `unknown` observation must be an accepted reconci... |
| `result-unknown-unregistered-attempt-id` | refuse: result_attempt_unresolved | DIVERGES | unsupported accepted observation state | refused (fail closed) at the Control Plane run before the result is read: the fixture's validated `unknown` observation must be an accepted reconci... |
| `trailing-line-break-digest` | refuse: schema_violation | REFUSED | `schema_violation`: typed refusal profile: invalid journal proposal commitment |  |
| `undeclared-member-outside-extensions` | refuse: undeclared_member | REFUSED | `undeclared_member`: execution_result has unsupported member(s): injected_member |  |
| `unpaired-surrogate-text` | refuse: schema_violation | REFUSED | `schema_violation`: input text is not valid Unicode (unpaired surrogate) |  |
<!-- END FIXTURE TABLE -->

Totals: 20 ACCEPTED, 52 REFUSED, 6 DIVERGES, 0 NOT-EXERCISED.

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
| `result-unknown-null-attempt-id-null-observation` | result_attempt_unresolved | REFUSED | `result_attempt_unresolved`: execution result status 'unknown' names no attempt row of the export (a null attempt_id or an id that matches no row i... |  |
| `control-plane-attempted-row-after-acknowledged` | attempt_transition | REFUSED | `attempt_transition`: Control Plane attempt syn-attempt-1 row status 'attempted' may not follow 'acknowledged' |  |
| `reasons-minimum-unreadable-input-without-reason` | reasons_minimum | DIVERGES | accepted | Replay does not derive the implied-reasons floor of a completed journal check (contract 39-E) |
| `reasons-match-extra-reason-on-check-row` | journal_unbound_completion | DIVERGES | accepted | Replay binds a completion to any check whose reasons are a superset; the contract allows only the closed POST_JOURNAL_GATE_CODES as additional reasons (39-A) |
<!-- END PROBE TABLE -->

## Mapping from contract code to Replay message

<!-- BEGIN MAPPING TABLE -->
| Contract code | Replay message pattern | Emitted by Replay | Note |
|---|---|---|---|
| `attempt_identity_changed` | `changed its effect_id or decision_id between lifecycle rows` | yes |  |
| `attempt_started_at_changed` | `started_at changed between lifecycle rows\|conflicting content under immutable attempt_id` | yes |  |
| `attempt_transition` | `executor attempt .* event .* may not follow\|Control Plane attempt .* row status .* may not follow\|conflicting content under immutable terminal Control Plane attempt` | yes | executor events and Control Plane rows move only along the contract's attempt state machines |
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
| `reasons_minimum` | `completion's reasons lack what its own recorded inputs imply` | no | Replay does not derive the implied-reasons floor of a completed journal check |
| `recovery_observation_status` | `a recovery report is only carried by results unknown or observed` | yes |  |
| `recovery_observations_mismatch` | `recovery_observations differ from the result report` | yes |  |
| `recovery_report_incomplete` | `(operation_digest\|claim_state\|effect_id\|reason) is required for an? \w+ recovery report` | yes |  |
| `recovery_retry_eligible` | `unsupported retry eligibility` | yes |  |
| `recovery_state_mismatch` | `recovery report observed-state contradiction` | yes |  |
| `repeated_record` | `lifecycle repeats a record` | yes |  |
| `repeated_start_event` | `executor attempt .* repeats its attempted event` | yes |  |
| `resolution_checks_out_of_order` | `resolution checks are out of journal order` | yes |  |
| `result_attempt_unresolved` | `names no attempt row of the export` | yes | a null attempt_id and an id that matches no row are both refused |
| `result_binding_mismatch` | `execution_result identifiers do not match execution envelope\|execution_result\.observation\.effect_id conflicts with committed operation` | yes |  |
| `result_state_matrix` | `the producer status matrix contradicts the execution result` | yes |  |
| `schema_violation` | `is required\|must be an (object\|array)\|must be object or null\|not \{\}\|is not a validated observation\|input text is not valid Unicode\|invalid journal proposal commitment` | yes | Replay emits this code for structural failures (since step B also for `{}` and for a recovery report in observations) |
| `status_terminal_mismatch` | `execution result status .* contradicts the terminal attempt event` | yes |  |
| `terminal_event_missing` | `execution result status .* contradicts the terminal attempt event 'attempted'` | yes |  |
| `undeclared_member` | `has unsupported member\(s\)\|recovery report has undeclared members\|unsupported/missing evidence fields` | yes |  |
| `unknown_enum_value` | `is not a recovery status\|is not a declared value` | yes |  |
| `unknown_state_mismatch` | `recovery report observed-state contradiction\|unknown result observed-state contradiction` | yes |  |
| `unknown_with_validated_observation` | `unknown result cannot carry a validated (applied/partial )?observation` | yes |  |
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
| RP-5 legacy layout | Refused since step B (`schema_violation`: `observations` lists validated observations only, a report has no `state`). Both the mirror alone and the mirror together with `recovery_observations` are refused (fixtures `recovery-report-in-observations-member`, `mixed-layout-observations-disagree-with-result`). |
| RP-6 unknown with a validated observation (narrowed, owner item 14) | Result `unknown` may carry a validated observation whose state is `absent` or `unknown`, with `observed_state` equal to `observation.state` (`unknown_state_mismatch` otherwise). `unknown` with a validated `applied`/`partial` observation is refused whatever the terminal event (`unknown_with_validated_observation`): enforced since step B (`ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATION` is True) now that the pinned runtime reports a lost ack that is then observed as `reconciled` (observed partial: `partial`). The carry applies to a validated `absent` observation only: a validated `unknown` observation cannot be emitted by the Control Plane today, so `executor-unknown-validated-unknown-after-ambiguous-dispatch` stays a strict xfail. |
| RP-7 closed enumerations | Enforced (`unknown_enum_value`) for result, event and Control Plane attempt statuses, `time_source` and the validated observation state; `denied` is a valid event status. |
| RP-8 closed members, `x-` keys | Enforced for attempt rows, events and Control Plane attempt rows as well (`undeclared_member`, `invalid_extension_key`); the extension name pattern is the contract's. P3b (owner item 16): `x-` extensions are accepted and preserved verbatim on resolution journal events and inputs, resolution checks and check inputs (the journal-to-check content binding ignores `extensions`), and on Control Plane attempt rows (closed sets, extras only via `extensions`). |
| RP-9 reconciled marker | Valid only as the whole acknowledgement of a lone `acknowledged`/`partial` row, and exactly `true`. |
| RP-10 `executed` without observation | Refused (`executed_without_observation`). |
| RP-11 optional members | `observations`, `recovery_observations`, `control_plane_attempts`, result `decision_id`/`effect_id`, attempt `operation_digest` are no longer required; members the contract requires still are (`schema_violation`). |
| RP-12 export-level `extensions` | Retained as the record `executor_export_extensions`. |

### Lifecycle contract `e5fe3822` (attempt state machines, result binding, schema checks)

| Rule | Replay |
|---|---|
| `attempt_transition` (decision 37) | Executor attempt events and Control Plane attempt rows move only along the contract's state machines (the tables `EXECUTOR_ATTEMPT_TRANSITIONS` and `CONTROL_PLANE_ATTEMPT_TRANSITIONS` equal the vendored ones, asserted by a test). A closed attempt is never reopened and never receives a later contradicting record. Previously an executor `failed`/`executed`/... reopen was accepted when the other evidence agreed. |
| `attempt_identity_changed` | All rows of one Control Plane attempt carry one `effect_id` and one `decision_id`. |
| `result_attempt_unresolved` (decision 40) | A result whose status claims an attempt (`failed`, `partial`, `unknown`, `executed`, `reconciled`) names an attempt the export carries; a null id and an unknown id are both refused, before the terminal-event comparison and the observation rules. Replay also accepts a Control Plane attempt row of the export as the named attempt (the Control Plane attempt namespace), which the contract validator does not model (its documents have no Control Plane attempt rows beside an executor result). |
| `result_binding_mismatch` | The result's `effect_id`/`decision_id` and the observation's `effect_id` must equal the attempt's (Replay compares with the execution envelope the attempt rows are bound to). |
| `result_state_matrix` | The producer's status matrix is checked explicitly (a port of the contract rule, tested against the vendored one over a grid), not only through the Control Plane acknowledgement cross-check. |
| `schema_violation` for text | Text that is not valid Unicode (an unpaired surrogate, in a value or a member name) anywhere in an input is refused; the extension-name and digest patterns match the whole string (a trailing line break is no longer accepted). |

Not enforced (strict-xfail probes, the contract code is the expectation): `reasons_minimum` (a completed journal check's
reasons must include what its own recorded inputs imply) and the closed set of additional reasons on a check row
(`POST_JOURNAL_GATE_CODES`, `reasons_match` 39-A). Replay binds a completion to any check whose reasons are a superset.
Enforcing them changes which real Control Plane runs import, so it needs its own decision and a re-capture.

Replay behaviour that goes beyond the contract, kept on purpose:

- `execution_result.observation: {}` is refused since step B with `schema_violation` (the contract allows only null, owner item 13).
- Route B normal executions (F-28): `control_plane_evidence` of a normal atomic-local execution carries `local_authority_effect_profile`, `claim_id`, `linearized_at` and `authority_receipt`. The contract leaves `control_plane_evidence` an open object; Replay accepts exactly these four members together, only on a newly executed result, with the receipt bound to the result by attempt, effect, decision and claim identity and an active grant. They describe the destination's own authority check and establish nothing beyond the validated observation.
- A validated `unknown` observation on result `unknown` is refused until the Control Plane emits it (see RP-6).

Replay now matches the contract on the null-observation rule (owner item 15, reversing the P3 relaxation): whenever the observation is null, `observed_state` is `unknown` for every result status (`null_observation_state_mismatch`). This is also what real denied exports carry.

## Refreshing the vendored copy

```
git -C open-decision-evidence-standard checkout <commit>
python open-decision-evidence-standard/contracts/tools/vendor_contract.py copy \
  --contract execution-attempt-lifecycle \
  --dest tests/contracts/execution-attempt-lifecycle \
  --role consumer --level L --odes-commit <commit>
```

Last refresh: 2026-10-22, ODES `59ca4c797b4c0700b581815a53b113a60bda1c67` (#136: the missing-attempts rule; `validate.py` `405812fe...`, `README.md` `336cab61...`, `schema.json` unchanged `1fc55d6f...`; three new invalid fixtures, which Replay refuses without the contract code, see DIVERGES above), with `--role consumer --level L`.

`python open-decision-evidence-standard/contracts/tools/vendor_contract.py check --dest tests/contracts/execution-attempt-lifecycle`
verifies the copy against its `CONTRACT.json`.

Then set `ODES_COMMIT` in the test, run `PYTHONPATH=.:src python -m pytest -q tests`, regenerate the tables with
`PYTHONPATH=src python -m tests.test_contract_lifecycle_conformance`, paste them between the markers above, and update
`DECLARED`, `NOTES` and `NOT_EXERCISED` in the test for every fixture whose status changed. Never edit the vendored files by hand:
the drift test fails on a modified, missing or unlisted file.
