# Contract conformance: execution-attempt-lifecycle (consumer)

Replay is the consumer of the ODES `execution-attempt-lifecycle` contract (ODES issue
cogno-us/cognous-control-plane#38, step P2).

| | |
|---|---|
| Contract | `execution-attempt-lifecycle` `0.1.0-draft` (draft, not frozen; any change may break) |
| Vendored from | `cogno-us/open-decision-evidence-standard` at `d1e17fa155140f371050aff4b61da0f2cc84f44a`, in `tests/contracts/execution-attempt-lifecycle/` (`CONTRACT.json` lists the SHA-256 of every file) |
| Role | consumer |
| Level claimed | `L` (structure and lifecycle rules), **only for the fixtures with status ACCEPTED or REFUSED below**. It is not claimed for the DIVERGES and NOT-EXERCISED fixtures, and the structure half (closed member sets, closed enumerations) is not claimed beyond those fixtures: the probes show it is not enforced below the export root (F-P2-RP-7, F-P2-RP-8). |
| Test | `tests/test_contract_lifecycle_conformance.py` (test-only; nothing under `src/` changed) |

## How it is tested

The vendored fixtures are abstract (synthetic ids). Each fixture family has an adapter that builds the minimum real
Replay input and calls the real code through `import_bounded_workflow`:

- executor rows and result: planted over the real captured exports in `tests/fixtures/route_b_post_commit/`
  (recovery reports) and `tests/fixtures/security_runtime_valid/` (validated observations), with the real Control Plane run;
- `control_plane_attempts`: replace `attempts` of the real run (`_validate_repaired_run`);
- `resolution_journal` / `resolution_checks`: replace `check_events` / `resolution_checks` (`refusal_evidence.validate_run`).

Completions are limited to what Replay needs and the contract leaves abstract: synthetic ids and the synthetic
observation time are rebound to the capture's, the attempt row takes the capture's `operation_digest` / `created_at`,
a validated applied observation takes the capture's `destination_state` when the fixture has none or `{}`, and
`observations` is mirrored from the result when the fixture has no such member (Replay requires it, F-P2-RP-11).
Every REFUSED fixture has a control: the same adapter accepts it once only the planted defect is repaired.
Replay does not emit contract codes, so a refusal counts only if its message matches the agreed pattern in the mapping
table. A DIVERGES fixture is a strict xfail that states the contract expectation; a NOT-EXERCISED fixture is a test
that asserts the stated reason.

## Fixtures

<!-- BEGIN FIXTURE TABLE -->
| Fixture | Contract expects | Status | Replay does | Note |
|---|---|---|---|---|
| `control-plane-normal-attempted-acknowledged` | accept | DIVERGES | conflicting content under immutable attempt_id <id> | F-P2-RP-2: started_at differs between the two rows; Replay treats it as an attempt invariant |
| `control-plane-reconciled-existing-acknowledged` | accept | ACCEPTED | accepted |  |
| `control-plane-reconciled-existing-partial` | accept | ACCEPTED | accepted |  |
| `executor-normal-attempted-executed-observed` | accept | DIVERGES | historical local observation cannot claim CP validation | F-P2-RP-1: result observed with attempted/acknowledged/newly_executed true is refused |
| `executor-normal-observations-member` | accept | DIVERGES | moltbot_export has unsupported member(s): recovery_observations | F-P2-RP-3: refused first for the unknown member recovery_observations; with it removed, F-P2-RP-1 refuses it |
| `executor-observed-effect-free-reconcile-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-ack-unobserved` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-hold-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-observation-route-b` | accept | ACCEPTED | accepted |  |
| `executor-unknown-recovery-separate-member-route-b` | accept | DIVERGES | moltbot_export has unsupported member(s): recovery_observations | F-P2-RP-3 (member recovery_observations); without it F-P2-RP-4 (observations [] is refused) |
| `executor-unknown-recovery-unavailable-route-b` | accept | ACCEPTED | accepted |  |
| `extension-namespace-member-preserved` | accept | ACCEPTED | accepted | accepted; top-level extensions are not retained (F-P2-RP-12) |
| `resolution-checks-overlap-a-completes-first` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-completion-order` | accept | ACCEPTED | accepted |  |
| `resolution-checks-overlap-b-completes-first-listed-open-order` | accept | ACCEPTED | accepted |  |
| `control-plane-dropped-start-record` | refuse: missing_start_record | REFUSED | Control Plane attempt <id> lifecycle lacks its attempted start record |  |
| `control-plane-start-row-reconciled-existing-false` | refuse: invalid_reconciled_marker | REFUSED | Control Plane attempt <id> carries an invalid reconciled_existing marker |  |
| `effect-free-reconcile-claims-attempt` | refuse: effect_free_reconcile_claims_attempt | REFUSED | an effect-free reconcile result cannot claim an attempt, acknowledgement or new effect |  |
| `effect-free-reconcile-state-mismatch` | refuse: recovery_state_mismatch | REFUSED | recovery report observed-state contradiction |  |
| `executor-dropped-start-event` | refuse: missing_start_event | REFUSED | executor attempt <id> events do not start with attempted |  |
| `executor-dropped-terminal-event` | refuse: terminal_event_missing | REFUSED | execution result status 'executed' contradicts the terminal attempt event 'attempted' |  |
| `executor-terminal-failed-vs-status` | refuse: status_terminal_mismatch | NOT-EXERCISED | not run | result executed with observation null is refused first by a Replay-only rule (importers.py:1384-1385, an attempt without a validated observation mu... |
| `executor-unknown-recovery-state-contradiction` | refuse: unknown_state_mismatch | REFUSED | recovery report observed-state contradiction |  |
| `executor-unknown-with-validated-observation` | refuse: unknown_with_validated_observation | DIVERGES | execution result status 'unknown' contradicts the terminal attempt event 'executed' | F-P2-RP-6: no rule; refused only by the terminal-event rule, accepted when the terminal event is unknown |
| `extension-key-without-x-prefix` | refuse: invalid_extension_key | REFUSED | moltbot_export.extensions names must start with 'x-': trace | rule order: refused here before F-P2-RP-1 would be |
| `recovery-applied-missing-operation-digest` | refuse: recovery_report_incomplete | REFUSED | execution_result.observation.operation_digest is required for an applied recovery report |  |
| `recovery-hold-missing-reason` | refuse: recovery_report_incomplete | REFUSED | execution_result.observation.reason is required for a hold recovery report |  |
| `recovery-observations-differs-from-result` | refuse: recovery_observations_mismatch | DIVERGES | moltbot_export has unsupported member(s): recovery_observations | F-P2-RP-3: refused only because the member is unknown; no mismatch rule exists |
| `recovery-report-in-observations-member` | refuse: schema_violation | DIVERGES | accepted | F-P2-RP-5: legacy layout is the layout Replay requires, so it is accepted |
| `recovery-retry-eligible-true` | refuse: recovery_retry_eligible | REFUSED | unsupported retry eligibility |  |
| `resolution-checks-sequential-reorder` | refuse: resolution_checks_out_of_order | REFUSED | typed refusal profile: resolution checks are out of journal order |  |
| `result-status-unknown-enum-value` | refuse: unknown_enum_value | DIVERGES | a recovery report is only carried by results unknown or observed | F-P2-RP-7: refused only because a recovery report needs unknown/observed; a consistent unknown status is accepted |
| `undeclared-member-outside-extensions` | refuse: undeclared_member | REFUSED | execution_result has unsupported member(s): injected_member | rule order: refused here before F-P2-RP-1 would be |
<!-- END FIXTURE TABLE -->

Totals: 11 ACCEPTED, 13 REFUSED, 8 DIVERGES, 1 NOT-EXERCISED.

## Probes beyond the fixtures

Each probe is first checked against the vendored reference validator, then run through Replay.

<!-- BEGIN PROBE TABLE -->
| Probe | Contract (vendored validator) | Status | Replay does | Finding |
|---|---|---|---|---|
| `undeclared-member-attempt-row` | undeclared_member | DIVERGES | accepted | F-P2-RP-8 |
| `undeclared-member-event-row` | undeclared_member | DIVERGES | accepted | F-P2-RP-8 |
| `undeclared-member-control-plane-attempt-row` | undeclared_member | DIVERGES | accepted | F-P2-RP-8 |
| `undeclared-member-recovery-report` | undeclared_member | REFUSED | execution_result.observation recovery report has undeclared members: injected |  |
| `extension-bad-key-attempt-row` | invalid_extension_key | DIVERGES | accepted | F-P2-RP-8 |
| `extension-bad-key-result` | invalid_extension_key | REFUSED | execution_result.extensions names must start with 'x-': trace |  |
| `reconciled-marker-extra-acknowledgement-member` | invalid_reconciled_marker | REFUSED | Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `reconciled-marker-non-boolean` | invalid_reconciled_marker | REFUSED | Control Plane attempt syn-attempt-1 carries an invalid reconciled_existing marker |  |
| `reconciled-marker-on-failed-row` | invalid_reconciled_marker | DIVERGES | accepted | F-P2-RP-9 |
| `reconciled-marker-on-unknown-row` | invalid_reconciled_marker | DIVERGES | accepted | F-P2-RP-9 |
| `enum-result-and-terminal-event-status` | unknown_enum_value | DIVERGES | accepted | F-P2-RP-7 |
| `enum-middle-event-status` | unknown_enum_value | DIVERGES | accepted | F-P2-RP-7 |
| `enum-control-plane-attempt-status` | unknown_enum_value | DIVERGES | accepted | F-P2-RP-7 |
| `enum-control-plane-time-source` | unknown_enum_value | DIVERGES | accepted | F-P2-RP-7 |
| `enum-recovery-status` | unknown_enum_value | REFUSED | execution_result.observation.status is not a recovery status |  |
| `enum-validated-observation-state` | unknown_enum_value | DIVERGES | rejected/substituted evidence promoted to accepted observation | F-P2-RP-7 |
| `recovery-report-on-executed-result` | recovery_observation_status | REFUSED | a recovery report is only carried by results unknown or observed |  |
| `executed-result-with-null-observation` | valid | DIVERGES | attempt without validated observation must remain unknown | F-P2-RP-10 |
| `export-without-observations-member` | valid | DIVERGES | versioned Moltbot export missing: observations | F-P2-RP-11 |
<!-- END PROBE TABLE -->

## Mapping from contract code to Replay message

<!-- BEGIN MAPPING TABLE -->
| Contract code | Replay message pattern | Emitted by Replay | Note |
|---|---|---|---|
| `attempt_without_events` | `executor attempt .* has no attempt events` | yes |  |
| `duplicate_attempt_row` | `duplicate executor attempt row` | yes |  |
| `duplicate_check_id` | `duplicate/empty resolution check id` | yes |  |
| `effect_free_reconcile_claims_attempt` | `an effect-free reconcile result cannot claim an attempt` | yes |  |
| `event_order` | `attempt_events\[\d+\] (event_id is repeated or out of order\|created_at is missing or out of order)` | yes |  |
| `invalid_extension_key` | `extensions names must start with 'x-'` | yes |  |
| `invalid_reconciled_marker` | `invalid reconciled_existing marker` | yes |  |
| `journal_check_reused` | `completed journals reuse one actual resolution check` | yes |  |
| `journal_protocol` | `journal (missing opening or already closed\|binding changed\|input missing)\|duplicate journal opening` | yes |  |
| `journal_unbound_completion` | `completed journal differs from actual resolution check` | yes |  |
| `missing_start_event` | `executor attempt .* events do not start with attempted` | yes |  |
| `missing_start_record` | `lifecycle lacks its attempted start record` | yes |  |
| `observations_mismatch` | `accepted executor observations differ from result` | yes | Replay requires the recovery report to be mirrored in observations (legacy layout) |
| `recovery_observation_status` | `a recovery report is only carried by results unknown or observed` | yes |  |
| `recovery_observations_mismatch` | `recovery_observations differ from the result report` | no (proposed) | Replay does not know the member |
| `recovery_report_incomplete` | `(operation_digest\|claim_state\|effect_id\|reason) is required for an? \w+ recovery report` | yes |  |
| `recovery_retry_eligible` | `unsupported retry eligibility` | yes |  |
| `recovery_state_mismatch` | `recovery report observed-state contradiction` | yes |  |
| `repeated_record` | `lifecycle repeats a record` | yes |  |
| `repeated_start_event` | `executor attempt .* repeats its attempted event` | yes |  |
| `resolution_checks_out_of_order` | `resolution checks are out of journal order` | yes |  |
| `schema_violation` | `recovery report in observations \(legacy layout\)` | no (proposed) | Replay has no schema layer; for the legacy layout the proposed wording is used |
| `status_terminal_mismatch` | `execution result status .* contradicts the terminal attempt event` | yes |  |
| `terminal_event_missing` | `execution result status .* contradicts the terminal attempt event` | yes | Replay does not distinguish a missing terminal event from a mismatched one |
| `undeclared_member` | `has unsupported member\(s\)\|recovery report has undeclared members` | yes |  |
| `unknown_enum_value` | `is not a recovery status\|is not a declared (status\|value)` | partly | Replay checks only the recovery report status (the rest uses the proposed wording) |
| `unknown_state_mismatch` | `recovery report observed-state contradiction\|null observation cannot establish observed state` | yes |  |
| `unknown_with_validated_observation` | `unknown result cannot carry a validated observation` | no (proposed) | no Replay rule; see finding |
| `unsupported_contract_version` | `contract_version` | no (proposed) | Replay exports carry no contract_version member; out of scope |
<!-- END MAPPING TABLE -->

## Findings

Evidence is `src/agent_replay_bundle/importers.py` unless stated. The product code is unchanged by this work.

- F-P2-RP-1: a result `observed` with `attempted` true is refused, with or without Control Plane evidence (1467-1468 and 1459-1464). Replay only knows `observed` as an effect-free historical observation. Fixtures `executor-normal-attempted-executed-observed`, `executor-normal-observations-member`.
- F-P2-RP-2: `started_at` is treated as an immutable attempt invariant (663-664, 112-118); the contract fixture varies it across the lifecycle rows. Fixture `control-plane-normal-attempted-acknowledged`. The contract does not say `started_at` is invariant.
- F-P2-RP-3: `recovery_observations` is not in `MOLTBOT_EXPORT_MEMBERS` (346-351), so any export carrying it is refused as an undeclared member (812). Fixtures `executor-normal-observations-member`, `executor-unknown-recovery-separate-member-route-b`, `recovery-observations-differs-from-result`; Replay has no mismatch rule.
- F-P2-RP-4: Replay requires a recovery report to be mirrored in `observations` (1371-1373); the new layout (`observations` empty) is refused. Fixture `executor-unknown-recovery-separate-member-route-b`.
- F-P2-RP-5: because of F-P2-RP-4 the legacy layout is accepted (and retained as `executor_recovery_report`). The README says consumers accept both during alpha while the draft refuses the legacy layout, so the fixture `recovery-report-in-observations-member` contradicts the README. Owner decision needed.
- F-P2-RP-6: no rule for `unknown_with_validated_observation`. The fixture is refused only through the terminal-event rule (1345-1351); with terminal event `unknown` Replay accepts it.
- F-P2-RP-7: closed enumerations are not enforced: a consistent result status `finished` (with a `finished` terminal event), a middle event status, a Control Plane attempt `status` and `time_source` outside the enumeration are accepted and retained verbatim (not coerced). Only the recovery report status is checked (207-208). An unknown validated observation `state` is refused, but incidentally.
- F-P2-RP-8: closed member sets and `x-` keys are enforced only for the export root, `execution_result`, the recovery report, `producer_profile` and `repository` (812-818, 205, 1357-1361). Undeclared members and bad extension keys in attempt rows, event rows and Control Plane attempt rows are accepted.
- F-P2-RP-9: the `reconciled_existing` marker is accepted on a single row of any status except `attempted` (1297-1298); the contract allows it only on `acknowledged` or `partial`.
- F-P2-RP-10: a result `executed` with observation null is refused (1384-1385); the vendored validator accepts it. Replay is stricter than the contract (not covered by a fixture).
- F-P2-RP-11: Replay requires `observations`, `control_plane_evidence` and `rejected_observations` (1362-1364) and, for a versioned export, `attempt_identity` and `control_plane_attempts` (854); the contract leaves them optional.
- F-P2-RP-12: the export-level `extensions` member is validated (1358) and then dropped: it is in no retained record. The contract requires consumers to preserve it. Extensions on attempt rows are retained.

Checked and conforming: undeclared members in `execution_result` and in recovery reports; `x-` keys at the export root, in the result and in the observation; the `reconciled_existing` marker on a start row, with extra acknowledgement members, non-boolean, or across several rows; dropped start record; repeated record; recovery report completeness, `retry_eligible`, observed-state rules and the effect-free reconcile rules; the resolution-check ordering rule (overlapping checks in either order, sequential checks in order).

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
