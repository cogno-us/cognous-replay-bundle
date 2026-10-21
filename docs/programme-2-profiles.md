# Programme-2 opt-in profiles (operation identity, rule revision, freshness, merge record, reversibility, dedupe)

Replay accepts and retains the run-record members of the opt-in Control Plane profiles for one exact revision, Control Plane
`e77fe0ee8714617899592528e660a80fbb2e864a` (constants `CONTROL_PLANE_P2_REVISION`, `BOUNDED_P2_PROFILE`), paired with the runtime
`cab4d9abc651c7efbafb429798d2c908f048bf5c` (`MOLTBOT_P2_REVISION`, `MOLTBOT_P2_PROFILE`). The generation was first tied to Control Plane
`128eaa5e` (Replay 8e32975d), then to `3755c71a` (Replay 3c056cf8), `3cd17ead`, `6093aca7`, `2bac7875` and `5c474ba8`; every earlier tie is replaced, not kept (one exact revision, never a range). Every earlier generation behaves exactly
as before; with every profile off the new generation imports a run exactly as the previous one does.

| Profile | Members Replay accepts and retains |
|---|---|
| `operation-identity/0.1` | lists `operations`, `operation_renewals`, `attempt_joins` (record types `operation`, `operation_renewal`, `attempt_join`); `operation_id`/`operation_issuer` in a binding's `runtime_authority`; `check_id` on an effect-time refusal |
| `rule-revision/0.1` | lists `rule_revisions`, `rule_revision_refusals` (record types `rule_revision`, `rule_revision_refusal`); `rule_identity` on decisions and refusals |
| `freshness/0.1` | lists `age_extensions`, `age_extension_refusals`, `recovery_runs` (record types `age_extension`, `age_extension_refusal`, `recovery_run`); `evaluated_at`/`recorded_at` on decisions and attempts, `recorded_at` on resolution checks, `evaluated_at`/`deadline` on refusals; `deadline`, `age_bound_seconds`, `extension_id`, `nonce`, the phases `overdue` and `expired` on journal events; `age_basis` and the read state `nonce_mismatch` on inputs |
| `merge-record/0.1` (N4) | lists `merge_records`, `compensation_obligations` (record types `merge_record`, `compensation_obligation`); `merged_into` on attempt joins |
| `reversibility/0.1` (N4) | list `snapshot_uses` (record type `snapshot_use`); the action-class member `x-reversibility` travels inside the retained journal rows as written |
| `dedupe-ttl/0.1` (N4) | list `dedupe_escalations` (record type `dedupe_escalation`); an attempt `unknown` with error `destination_in_progress` |
| `terminal-revocation/0.1` | no member of its own: its rows are an ordinary decision or refusal whose reason is `grant_revocation_recorded` (registry label 0.2 only) with a `successor_grant_revision` reopen condition, retained verbatim |

Members inside rows Replay already retained (decisions, attempts, refusals, resolution checks, journal events) stay in the retained
row verbatim. The lists become records, in source order after the existing evidence records, and `extend_retained_inputs`
rebuilds them for the Evidence Pack's re-validation. With no profile member in the record nothing is added.

## Reason registry labels

The Control Plane stamps a decision, refusal, check or journal row with `runtime-authority-reasons/0.2` only when a reason is a code
that only the 0.2 registry has (0.2 is a superset of 0.1: the original 121 codes plus the profile codes); every other row keeps
`/0.1`. For this generation Replay accepts exactly those two labels on those rows and refuses any other as `unknown_enum_value`.
Earlier generations still accept `/0.1` only. Replay does not check that a label matches the codes of its row (the verifier does).

## Executor pairing

The runtime `cab4d9ab` (main after `79f39166`, which was main after `6b16962d`, which was main after `c4a05883`, which was main after `62a5cc15`, which was main after #121; `11de097c` was main after #116: atomic-route grant status monotonicity, envelope binding, strict instants, exception class names only; the earlier ties were `fc034d14`, `7170da59`, `11de097c`, `62a5cc15`, `c4a05883`, `6b16962d` and `79f39166`, replaced not kept, and an export of any of them is now refused) exports the same producer contract as
before; its export is accepted only with this Control Plane revision, and an export of any other runtime revision (`3024ef6e`,
`4a83b175`, ...) is refused as an unsupported combination with it, and the reverse. The key itself is not in the export.
Captured pairs: `tests/fixtures/programme2_paired` (adapter route and atomic route, default and with operation identity).

Known limit, not changed here: the Control Plane's own claim issuance (`provision_local_execution_claim`) opens a decision-stage
journal check next to a claim-stage resolution check, and Replay refuses that record at every generation (`journal_check_reused`).
The atomic captures therefore use the record taken before claim issuance (see their `PROVENANCE.json`).

## Refusals

Refusal codes are the ODES contract codes (`operation-identity`, `rule-revision`, `freshness-clocks`, all `0.1.0-draft`) where a
contract rule is applied: `undeclared_member` (an unknown member is refused, never dropped), `schema_violation`,
`unknown_enum_value`, `timestamp_invalid`, `invalid_extension_key`, and the cross-row codes (`join_attempt_missing`,
`decision_operation_unadmitted`, `attempt_without_join`, `deadline_mismatch`, `deadline_members_incomplete`,
`expired_refusal_mismatch`, `rule_identity_unbacked`, `profile_member_missing`, and the others listed in
`programme2_profiles.py`). `x-` extensions are preserved on profile rows.

## What this does not do

- It does not re-derive the producer's decisions, verify any signer, or check the ODES sidecar contracts in full. That is the
  verifier's and the ODES validators' work. Replay checks structure and the references a retained record must still satisfy.
- It cannot tell that a profile was on: a record from which every profile member was removed is a profile-off record.
- Only the runtime `cab4d9ab` is paired with this generation; any other executor export is refused as an unsupported combination.
- Under freshness the observation time is judged against the service clock at reconciliation (`reconciled_at`), as the producer
  does; staleness is still relative to the evaluation time.
- A run with no decision (only extension or revision refusals) is refused as before ("resolution journal missing"), except a run
  whose decisions are all holds for `check_lease_unavailable`, which has no journal events by design.

Tests: `tests/test_programme2_profiles.py` and `tests/test_programme2_n4_and_pairing.py` (real captures in `tests/fixtures/programme2_profiles` and
`tests/fixtures/programme2_paired`, provenance recorded there).
