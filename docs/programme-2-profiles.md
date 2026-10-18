# Programme-2 opt-in profiles (operation identity, rule revision, freshness)

Replay accepts and retains the run-record members of three opt-in Control Plane profiles for one exact revision, Control Plane
`128eaa5e36fdff772fdc709581712dbeac046db3` (constants `CONTROL_PLANE_P2_REVISION`, `BOUNDED_P2_PROFILE`). Every earlier
generation behaves exactly as before; with every profile off the new generation imports a run exactly as the previous one does.

| Profile | Members Replay accepts and retains |
|---|---|
| `operation-identity/0.1` | lists `operations`, `operation_renewals`, `attempt_joins` (record types `operation`, `operation_renewal`, `attempt_join`); `operation_id`/`operation_issuer` in a binding's `runtime_authority`; `check_id` on an effect-time refusal |
| `rule-revision/0.1` | lists `rule_revisions`, `rule_revision_refusals` (record types `rule_revision`, `rule_revision_refusal`); `rule_identity` on decisions and refusals |
| `freshness/0.1` | lists `age_extensions`, `age_extension_refusals`, `recovery_runs` (record types `age_extension`, `age_extension_refusal`, `recovery_run`); `evaluated_at`/`recorded_at` on decisions and attempts, `recorded_at` on resolution checks, `evaluated_at`/`deadline` on refusals; `deadline`, `age_bound_seconds`, `extension_id`, `nonce`, the phases `overdue` and `expired` on journal events; `age_basis` and the read state `nonce_mismatch` on inputs |

Members inside rows Replay already retained (decisions, attempts, refusals, resolution checks, journal events) stay in the retained
row verbatim. The lists become records, in source order after the existing evidence records, and `extend_retained_inputs`
rebuilds them for the Evidence Pack's re-validation. With no profile member in the record nothing is added.

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
- Only the Control Plane record is accepted for this generation. No executor (runtime) revision is paired with it, so an executor
  export with this Control Plane revision is refused as an unsupported combination.
- Under freshness the observation time is judged against the service clock at reconciliation (`reconciled_at`), as the producer
  does; staleness is still relative to the evaluation time.
- A run with no decision (only extension or revision refusals) is refused as before ("resolution journal missing"), except a run
  whose decisions are all holds for `check_lease_unavailable`, which has no journal events by design.

Tests: `tests/test_programme2_profiles.py` (real captures in `tests/fixtures/programme2_profiles`, provenance recorded there).
