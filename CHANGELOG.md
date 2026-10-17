# Changelog

## Unreleased

- Contract alignment step A, P3b (ODES execution-attempt-lifecycle at a9db024c, owner decisions of 2026-10-17, second batch): a null observation requires `observed_state` `unknown` for every result status (`null_observation_state_mismatch`, restoring the strict rule); result `unknown` may carry a validated `absent`/`unknown` observation with `observed_state` equal to `observation.state` (`unknown_state_mismatch`), and a validated `unknown` reading is accepted as a Control Plane observation (reconciliation result `hold`, empty destination state) for that carry; the refusal of `unknown` with a validated `applied`/`partial` observation stays behind `ENFORCE_UNKNOWN_WITH_VALIDATED_OBSERVATION` (False) until the pins advance (P4). `x-` extensions are accepted and preserved on resolution journal events and inputs, resolution checks and check inputs (the journal-to-check binding ignores them); invalid keys refuse with `invalid_extension_key`. Still tolerated in step A and refused in step B: `observation: {}` (schema_violation) and a recovery report inside `observations`.

- Contract alignment (ODES execution-attempt-lifecycle 0.1.0-draft at e33d541a, P3): `ImportContractError` gains a `code` attribute carrying the contract refusal code (messages unchanged). The producer 2.0.0 executor export now accepts the new layout (`observations` = validated observations only, optional `recovery_observations`, `execution_result.observation` carries the report) and still tolerates the legacy layout (report mirrored in `observations`); the report is retained as `executor_recovery_report` either way. Closed member sets and closed enumerations are enforced for attempt rows, attempt events, results and Control Plane attempt rows (`denied` is a valid attempt-event status); extension names must match `^x-[a-z0-9][a-z0-9._-]*$`; export-level `extensions` are retained as the record `executor_export_extensions`. New refusals: result `observed` claiming an attempt, result `executed` without an observation, result `unknown` with a validated observation, a `reconciled_existing` marker outside a lone `acknowledged`/`partial` row. Members the contract leaves optional (`observations`, `control_plane_attempts`, result `decision_id`/`effect_id`, attempt `operation_digest`) are no longer required. A null observation no longer forces `observed_state` `unknown` except on `unknown` results. See `docs/contract-conformance-execution-attempt-lifecycle.md`.

- Contract conformance (ODES execution-attempt-lifecycle): Producer 2.0.0 imports now reject undeclared members inside `execution_result`; reject a Control Plane attempt row carrying a `reconciled_existing` marker unless it is the whole acknowledgement `{reconciled_existing: true}` of a lone non-start record; and accept the reserved `extensions` object (names `x-...`) at the export top level, in `execution_result` and in `observation`, retaining it inside the record. Extensions with other names, or that are not objects, reject.

- Route B (atomic local executor) post-commit failure exports now import (qualification F-24). A result `unknown` carrying a destination *recovery report* (`status` in `applied|partial|hold|unknown`, with `claim_state`, `retry_eligible: false`, optional `effect_id`/`operation_digest`, `reason`) is accepted when: the report has no undeclared members; `retry_eligible` is false; identity and digest, when present, match the envelope; `applied`/`partial` carry `claim_state`, `effect_id` and `operation_digest`; `hold`/`unknown` carry a `reason`; `observed_state` equals the report status for `applied`/`partial` and `unknown` otherwise; and the result stays `unknown` and unacknowledged. The report is retained as record type `executor_recovery_report` with finding M021 and is never read as a validated observation. Executor evidence may carry `failure_record_id` (attributable reference) and `failure_class` alongside a recovery report. The same report on an effect-free reconcile (result `observed`, no attempt, no acknowledgement, no new effect) is accepted too. Regressions: `tests/test_route_b_recovery_import.py` with three real captured exports (post-commit read failure, lost acknowledgement with reconciliation down, effect-free reconcile) plus a planted `hold` report.

- Remediation of three over-strict Producer 2.0.0 / journal checks that rejected legitimate real-producer shapes (genuine defects are still rejected): (1) an execution result `unknown` with terminal executor event `executed` is accepted only when `observation` is null and `observed_state` is `unknown` (route-C Control Plane observation unavailable); (2) a Control Plane attempt lifecycle that is a single record with `acknowledgement == {"reconciled_existing": True}` needs no `attempted` start record, while any other lifecycle without one is still rejected; (3) the "resolution checks are out of journal order" rule applies only between non-overlapping checks (one completes before the other opens), so concurrent checks may interleave. Unknown-member export test no longer emits skips. Runtime pin unchanged.
- Repin: the F5b executor generation now accepts the remediated runtime `4a83b175d2ef0e65a7ee22a0513bb94a5fdf3a6f` (runtime #100-#103) in place of `e20f92e1`. Control Plane and Manifest identities are unchanged.
- Executor (Moltbot) export import now rejects unknown members at the export top level, in `producer_profile` and in `repository` with `ImportContractError`, instead of silently dropping them (runtime issue #98, V1 scenario C12). Follows the documented rule that unsupported fields in typed records reject. Behaviour change: exports carrying extra members that previously imported now fail closed.
- Audit-defect detection (qualification F-06 / F-12). Producer 2.0.0 imports now reject: repeated executor attempt or destination effect rows; executor attempt events that are missing, repeated, out of `event_id`/`created_at` order, not started by `attempted`, or whose terminal event differs from the execution result status; an execution result that denies a newly executed effect the producer acknowledged. Control Plane journal imports now reject attempt lifecycles without their single `attempted` start record or with a repeated record, resolution checks that do not match the completed journal checks in order, duplicate attempt closeouts, and an attempt left uncertain (`attempted`/`unknown`/`failed`) without the closeout owed to an accepted applied/partial observation. Clean real-producer exports are unaffected. A downstream consumer must still compare `import_reports` and `semantics` of a retained bundle against a fresh import; Replay does not own that comparison.
- Runtime-authority and security-runtime imports now mark opened-only or interrupted resolution journal checks with a B006 warning and `reconstruction_partial`.
- A completed journal check is matched to a separately recorded resolution check by content; one resolution check can no longer substantiate two completed journals.
- A dangling or ambiguous explicit executor attempt reference now fails closed for every producer 2.0.0 profile (merged, refusal, runtime-authority and security), as it already did for the original 2.0.0 profile.
- Documented legacy HMAC coverage limits and the known limits of the legacy, W3 atomic and C8 paths.

- Added exact producer-v2 compatibility for Control Plane persistence repair `248d899634d9db3518e831bc7ab568a48733f825` while preserving the earlier `2ea9528e...` revision.
- Kept Reconstruction Bundle 0.2.0 because the persistence repair does not change the consumed bounded-record wire contract.
- Added real-producer persistence-repair qualification and fail-closed contradiction tests without promoting source-asserted provenance.

- Added explicit executor producer 2.0.0 / repaired Control Plane revision compatibility without relabeling legacy evidence.
- Preserved null and rejected observations, owning attempt records and observed-absence semantics in Reconstruction Bundle 0.2.0.
- Added real-producer qualification, generated examples and adversarial owner-record/assurance checks.

- Hardened bounded import with proposal -> decision -> envelope -> destination cross-record validation.
- Added namespace-aware execution-result attempt resolution and embedded observation/reconciliation checks.
- Rejects multiple authorization bindings in the single-proposal importer instead of forcing a match.
- HMAC now authenticates integrity metadata except the signature value itself; legacy HMACs require explicit handling or re-signing.
- Added Governor regression coverage for proposal, destination, attempt, envelope and HMAC metadata substitution.


## 0.2.0 - 2026-10-05

- Added revision-pinned legacy and bounded Control Plane import profiles.
- Added Moltbot Safe Execution Envelope 0.2.0 / SQLite evidence import.
- Added ordered lifecycle preservation for repeated attempt records.
- Added explicit lineage, commitment metadata and machine-readable loss reports.
- Added reconstruction-only semantics that do not renew authorization or create effects.
- Added conflict checks for immutable decision, attempt and effect identities.
- Added reconstruction HMAC documentation and redacted-derivative identity semantics.
- Added pinned Control Plane -> Moltbot Safe integration tests.

The 0.1 `AgentReplayBundle` API remains available for compatibility.
