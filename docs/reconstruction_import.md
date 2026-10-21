# Reconstruction import contract 0.2.0

## Scope

The 0.2.0 reconstruction API imports recorded producer evidence. It does **not**:

- rerun a model;
- reevaluate policy unless a caller performs that separately;
- renew an authorization;
- repeat an effect;
- convert a producer acknowledgement into destination verification; or
- convert synthetic local destination state into independently verified institutional delivery.

The importer's default semantics are therefore non-effecting.

## Supported producer profiles

| Profile | Producer | Version basis |
|---|---|---|
| `control-plane-legacy-replay@28350065` | `ReplayBundle` from Cognous Agent Control Plane | no embedded format version; pinned to commit `283500652d47a692fb0b99a1172a6d5faffbd9a7` |
| `control-plane-bounded-run@28350065` | `BoundedRunRecord` from Cognous Agent Control Plane | no embedded format version; pinned to the same commit |
| `moltbot-safe-envelope-0.2.0@6b0ba118` | Execution Envelope 0.2.0 plus SQLite effects, attempts and append-only attempt events | explicit envelope version plus pinned commit `6b0ba1185bcd390f71df947dda349415e4105f5f` |

The bounded adapter is also tested with Manifest v1.1 at
`46c950bed37fe3812000895430bc0312d29e37ce` and Alvorada Authority Context
0.1.0 (the governance revision is listed in the hub's `component-lock.json`).

Shape similarity is never treated as a version negotiation mechanism.

## Confirmed legacy mapping

The pinned legacy Control Plane serializer emits these producer names:

| Producer field | 0.2 reconstruction representation |
|---|---|
| `replay_bundle_id` | `metadata.source_bundle_id` |
| `actions[]` | ordered `SourceRecord(record_type="action_proposal")` |
| `decisions[]` | ordered `SourceRecord(record_type="policy_decision")` |
| `policy_traces[]` | ordered policy-trace records |
| `authority_records[]` | ordered authority records |
| `reliance_records[]` | ordered reliance records |
| `blocked_actions[]` | ordered blocked-action records |

The importer preserves producer field names inside each source record instead of
renaming record content and pretending the original commitment covered the
renamed form.

## Bounded-workflow mapping

The bounded producer is event-oriented:

- each `RuntimeDecision` is retained as an immutable source record;
- each occurrence in `attempts[]` is retained in source order as an attempt
  lifecycle transition;
- observations and reconciliations are retained independently;
- proposal `correlation_id`, manifest identifiers, decision/effect IDs,
  grant/revision, policy versions, requirement commitment and role-mapping
  version/digest are retained where supplied;
- blocked/held decisions retain their producer `reasons`;
- a decision's `result` must be a value the Control Plane emits (`authorized` or `hold`, the values of every captured run); any other value
  (`denied`, an empty string, a different case, a non-string) is refused with the code `unknown_enum_value`, as an unknown
  executor status is, instead of being retained as a complete `runtime_decision`.

Chronology across producers is not checked: the timestamps of the executor export (`created_at` of attempts and events,
effect and observation times) are not related to the Control Plane's `decided_at`, so an executor event may carry a time
before the decision that authorized it and the import does not refuse or flag that.

A Control Plane attempt ID and Moltbot Safe attempt ID are different namespaces.
A link is created only when producer evidence explicitly supplies the Moltbot
attempt ID, such as the pinned adapter acknowledgement. Shared decision/effect
identifiers can support lineage but do not establish attempt identity.

### Unknown members in the executor export

Following the runtime rule that "unsupported fields in typed records reject
rather than disappear" (`docs/runtime-authority-profile.md`), the executor
(Moltbot) export importer rejects, with `ImportContractError`, any member not
in the supported set at three levels: the export top level
(`execution_envelope`, `execution_result`, `effects`, `attempts`,
`attempt_events`, `producer_profile`, `repository`, `provenance`,
`attempt_identity`, `control_plane_attempts`, `observations`,
`control_plane_evidence`, `rejected_observations`), `producer_profile`
(`profile_id`, `profile_version`, `execution_envelope_version`) and
`repository` (`repository`, `revision`, `revision_status`). Such members are
never silently dropped. This applies to legacy and versioned exports alike.

## Authority Context identifiers

Two different values are intentionally retained:

1. the proposal's `authority_context_ref`, which is a **profile reference**;
2. the Control Plane authorization binding's `authority_context_id`, which is
   a **resolved context-instance identifier**.

At the pinned Moltbot adapter revision, its
`ExecutionOperation.authority_context_id` field carries the proposal profile
reference. The reconstruction representation labels that value as
`authority_context_profile_ref` to avoid silently converting it into the
Control Plane context-instance identifier.

The Control Plane `AuthorizationBinding` does not persist
`institution_id` or `authority_domain`. Moltbot Safe derives those values
from its trusted integration context. Reconstruction preserves that provenance;
it does not backfill the Control Plane record from caller assertions.

## Import report and value states

Each adapter emits an `ImportReport` containing:

- explicit field mappings;
- unmapped fields;
- missing dependencies;
- unsupported semantics;
- conversion warnings;
- redactions; and
- value-state findings.

When applicable, values are classified as `absent`, `unknown`,
`unavailable`, or `redacted`.

`reconstruction_complete` means the declared import contract was completely
represented. It does **not** mean an external effect was completed or
independently verified. `reconstruction_partial` means source dependencies or
semantics remain unresolved. Partial/unknown destination states remain visible.

## Commitment handling

The importer records the source commitment value, algorithm and canonicalization
profile. It independently checks only contracts it actually knows at the pinned
revision, including:

- proposal payload commitment;
- Moltbot execution-envelope payload commitment; and
- Control Plane effect identity from proposal commitment + grant ID + grant
  revision.

The bounded importer validates the supplied evidence as one cross-record chain:
the full RuntimeProposal commitment must equal the decision binding; applicable
proposal fields must equal the binding; the Execution Envelope operation must
equal the proposal and grant/effect-limit binding; and durable destination rows
must equal the committed operation for grant, target, amount, unit and decoded
payload. A copied operation digest is insufficient when the row content differs.

Execution-result attempt IDs are namespace-aware. Ordinary destination
execution resolves to a Moltbot attempt row. The pinned reconciliation path may
return a Control Plane attempt ID when no new destination attempt is created.
Dangling IDs and incompatible namespace/status combinations are rejected; the
two namespaces are never treated as identity-equivalent.

This adapter accepts one supplied RuntimeProposal/Execution Envelope operation.
Multiple authorization bindings are rejected rather than forced onto that
proposal. Missing optional evidence can make reconstruction explicitly partial;
contradictory supplied evidence is a contract error.

Other source-provided digests are retained as attributed producer claims unless
a documented verification profile checks them. A digest is never recomputed
over renamed or redacted content and represented as the original digest.

Conflicting content under an immutable decision, attempt or effect identity is
rejected. Embedded execution-result observations and Control Plane
reconciliations are checked against their enclosing effect/state contracts.

## Integrity and redaction

Reconstruction HMAC uses HMAC-SHA256 over canonical reconstruction content plus
its integrity metadata, with only the HMAC signature value blanked to avoid a
circular input. The authenticated metadata therefore includes HMAC kind,
algorithm, canonicalization profile, subject bundle ID, caller-supplied
`key_id` label and verification claim. Verification also requires the declared
subject to equal the actual bundle ID and the algorithm/profile to match the
implemented profile.

A verifier must possess the same shared secret. This provides shared-secret
export integrity; it is not a publicly verifiable issuer signature and does not
establish production key custody. `key_id` is merely an authenticated label
provided by the caller; the HMAC does not independently authenticate the
identity or custody of that key.

The `content-digest` entry (written by `redact_reconstruction_bundle`) is checked by
`verify_content_digest(bundle, required=True)`: it fails closed on a stale value, a
second entry, another algorithm or profile, a foreign `subject_bundle_id` and (when
`required`) on no entry. `arb check-examples` applies it to every reconstruction
example (`required=False`: a bundle without an entry has nothing to check). Loading
a bundle (`ReconstructionBundle.model_validate`) does **not** run it: a bundle with a
stale digest still loads, so a consumer that relies on the digest must call the
verifier. It is an integrity check, not authentication: whoever edits the content can
recompute the digest.

Redaction order is:

1. copy the source reconstruction;
2. assign a new bundle identity;
3. record `redacted_derivative -> source_bundle_id`;
4. modify the selected source records;
5. remove source integrity metadata;
6. downgrade affected original commitment checks to attributed claims; and
7. compute fresh integrity metadata for the derivative.

A stale HMAC or source digest is never presented as authenticating modified
content.

## Evidence classes

Source records default to `producer_reported`. Tests and downstream tooling
may label separately produced evidence as `locally_generated` or
`independently_checked`, but the importer does not manufacture either label.
Synthetic Moltbot SQLite observation is producer/local destination evidence, not
independent institutional verification.

## Producer 2.0.0 migration (Batch 4C-B)

Reconstruction Bundle remains **0.2.0**. `SourceRecord.data` preserves JSON null,
full reconciliation fields and attributed rejected content; no schema change or
lossy conversion is needed. This extends import compatibility, not evidence
assurance. Existing historical examples and constants keep their original pins.

| Executor contract | Executor revision | Control Plane revision | Selection |
|---|---|---|---|
| Legacy unversioned, envelope 0.2.0 | `6b0ba1185bcd390f71df947dda349415e4105f5f` | `283500652d47a692fb0b99a1172a6d5faffbd9a7` | Existing explicit legacy adapter default |
| Producer 1.0.0, envelope 0.2.0 | `1d308faf664c504b6e310db3c7a310153ef7b067` | `283500652d47a692fb0b99a1172a6d5faffbd9a7` | Existing versioned adapter default |
| Producer 2.0.0, envelope 0.2.0 | `177354e959cc78c59c1a776f018cfbfbf28c927b` | `2ea9528eeb87e14ff10f05de06473122b9df540f` | Explicit `control_plane_revision=CONTROL_PLANE_V2_REVISION` |
| Producer 2.0.0, envelope 0.2.0 | `177354e959cc78c59c1a776f018cfbfbf28c927b` | `248d899634d9db3518e831bc7ab568a48733f825` | Same v2 wire contract; exact persistence-repair revision via `CONTROL_PLANE_V2_PERSISTENCE_REVISION` |

The producer profile ID remains
`urn:cognous:profiles:moltbot-safe-executor-producer`. Unsupported combinations
fail, including a v2 export with the historical default Control Plane selection.
Both accepted v2 Control Plane revisions remain exact pins. The later revision
changes same-host record persistence (locking, reload, flush/fsync and atomic
replacement) but does not change the consumed `BoundedRunRecord` wire contract;
Replay therefore retains Reconstruction Bundle 0.2.0 and assigns the later
Control Plane evidence its own revision-specific producer profile.
The revision argument selects a decoder contract; it does not authenticate the
source repository. Source-asserted provenance and supplied independent-evidence
entries remain attributed source content. Replay does not independently establish
repository origin, authority, observation truth or delivery.

```python
from agent_replay_bundle import import_bounded_workflow, CONTROL_PLANE_V2_REVISION
bundle = import_bounded_workflow(
    retained_control_plane_record,
    proposal=original_proposal,
    moltbot_export=original_export,
    control_plane_revision=CONTROL_PLANE_V2_REVISION,
)
```

The v2 adapter retains:

- Actual result acknowledgement and `newly_executed`, even when `observation` is
  null and `observed_state` is unknown. Null confers no absence, rollback,
  verification or retry claim. Rejected/unavailable CP observation yields an
  informational B020 historical finding. Faithfully retained rejection is not
  conversion loss and does not make reconstruction partial.
- `executor_control_plane_evidence` with full attempt and reconciliation,
  rejection reasons, evaluation time and policy values. Copied executor
  reconciliation content must exactly match a supplied retained Control Plane
  reconciliation. Matching copies establish consistency only, not independent
  evidence or proof the supplied records are authentic.
- `rejected_executor_observation` with the rejected content unmodified and **no
  accepted lineage identifiers**. A wrong effect ID here is attributed rejected
  content. Its enclosing reconciliation still must identify the original effect.
- Both owning attempt namespaces. Supplied Control Plane attempts must match
  retained Control Plane attempt records; explicit acknowledgements link executor
  attempts without claiming identity equivalence. Reconciliation never discards
  the original executor attempt.
- Actual destination state and operation content. Accepted observations must bind
  correctly, agree with destination content, and satisfy the recorded temporal
  policy. No policy is reevaluated and no fresh observation is obtained by import.
- Historical local observations without pretending they have CP validation (M020).
  Historical `safe_to_retry` stays in the historical decoder. The repaired decoder
  preserves `observed_absent` and requires `retry_eligible=false`.

New examples in `examples/producer-v2/` were generated by
`scripts/generate_producer_v2_examples.py` (now in the qualification repository, `suites/cognous-replay-bundle/scripts/`; see `CROSS_COMPONENT_TESTS.md`) using the exact accepted producers.
Root-level bounded examples remain explicitly historical; no digests were edited
by hand. See [the checkpoint](workstreams/replay-producer-v2-checkpoint.md) for
executed scenarios, validation and downstream migration work.


### Reconstruction completeness and observation history

For the repaired producer profile, `reconstruction_complete` describes whether
supplied evidence was represented under the import contract. It does not describe
delivery success. Fully retained rejected/unavailable observations, unknown
acknowledgements and partial destination effects can all be completely
reconstructed. Missing dependencies or unmapped fields can still make the import
partial. Historical revision-selected decoder behavior is unchanged.

B020 reports historical rejection/unavailability only. It neither claims delivery
remains unresolved nor marks the import incomplete. Original records are retained.
`metadata.effect_observation_history` separates, for each exact effect identity:

- Rejected reconciliation indices and the latest reconciliation in the supplied
  Control Plane reconciliation array.
- The latest accepted observation (including its source index) and latest
  supported destination state. If the latest reconciliation rejected observation,
  the latter is unknown, while the older accepted observation remains visible.
  Recovery ending with an accepted applied observation reports applied.
- Acknowledgement lifecycle entries in their separate attempt-array order. An
  unknown attempt status is never rewritten as received acknowledgement.
- Latest recorded `retry_eligible` (false under the repaired contract, null when
  unavailable). Observed absence grants no permission to dispatch.

Ordering is scoped to the owning producer array and exact effect lineage. No
comparison of reconciliation timestamps, attempt timestamps, or unrelated local
historical observations establishes a combined timeline. Cross-sequence order is
explicitly `not_established`; freshness at import is `not_evaluated`. These are
recorded observations, not a new destination query or authority evaluation.

## Known limitations of legacy and non-V1 paths

These limits are recorded as found; the behavior is unchanged. None of these
paths is the V1 Control Plane path, and none of them authorizes, renews or
dispatches anything.

Legacy 0.1 replay bundles (`validator.py`, `redaction.py`, `signing.py`):

- The semantic validator does not reject duplicate action, decision or trace
  identities (action IDs are compared as a set and traces are looked up by a
  last-wins map), and it does not require a decision's referenced policy trace
  to describe the same action. A `valid` report does not establish unique or
  action-consistent identities.
- Legacy redaction copies any `redaction_metadata.redacted_fields` already
  present on the input into the output without checking those paths were
  redacted. Treat inherited entries as unverified claims. It also keeps an
  embedded `signature_metadata` unchanged unless `clear_signature_metadata` is
  set, so a redacted bundle can still show `signed: true` with a signature over
  the earlier content, and it leaves the task text and scope fields unless
  `redact_task` / `redact_scope` are set (see [redaction.md](redaction.md)).
  Re-sign derivatives and do not trust embedded signature state.
- The legacy HMAC limits and the `--secret` command-line exposure are described
  in [signing.md](signing.md).

Executor adapters:

- The legacy unversioned and producer-profile 1.0.0 adapters do not correlate
  retained `observations` with `execution_result.observation` or
  `observed_state`. Only producer-profile 2.0.0 enforces that equality, so a
  legacy or 1.0.0 import can retain observations that contradict the result.
- An executor export with no `producer_profile` is treated as a legacy
  unversioned export. If it also has no `repository`, the importer records the
  adapter's pinned legacy revision `6b0ba1185bcd390f71df947dda349415e4105f5f`
  as the executor revision. That revision is assigned by the adapter, not
  stated by the producer, and versioned identity and observation checks are not
  applied. V1 Control Plane exports always carry a producer profile, so the V1
  path does not reach this branch.

W3/C8 mappings (`w3_atomic_import.py`, `w3_c8_lineage.py`) are non-V1,
non-authorizing reconstructions:

- The W3 atomic importer accepts an observation that has no `decision_id`, and
  one whose `decision_id` differs from the caller's, and records it under the
  caller-supplied effect and decision identities. Only a stated, contradicting
  `effect_id` is rejected. Observation-to-decision binding is not established.
- The C8 importer does not key grant, approval or policy rows uniquely. Only the
  first grant row's revision is compared, and approval and policy coverage is
  checked by set membership, so conflicting duplicate rows can be retained in a
  complete reconstruction. Stop events are checked for internal order and a
  single effect, but are not bound to the authority claim or its operation
  commitment before the two are combined.


## Audit-defect checks on producer artifacts

The bounded import fails closed when the producer artifacts are internally inconsistent in ways that indicate a dropped, repeated, reordered or altered record. These checks are consistency checks over the retained records; they do not authenticate the producer or establish that the records are complete relative to the real world.

Executor producer 2.0.0 export:

- attempt rows and destination effect rows are unique;
- every executor attempt has attempt events, `event_id` strictly increases and `created_at` does not decrease across the export, the first event of an attempt is `attempted` and `attempted` is not repeated;
- when the execution result names an executor attempt, the status of that attempt's last event equals the result status;
- an acknowledged new effect cannot be reported as not newly executed.

Control Plane run (repaired profiles and later):

- each attempt lifecycle starts with its single `attempted` record and no lifecycle record is repeated verbatim;
- completed journal checks match the recorded resolution checks in order (by stage and inputs, with the journal's reasons a subset of the check's reasons) (a resolution check still substantiates at most one journal);
- closeouts are unique per attempt and observed state, and an attempt whose last record is `attempted`, `unknown` or `failed` has a closeout for every accepted applied or partial observation of its effect.

Limits: the order checks assume sequential checks and one array order per producer (no cross-array clock); the closeout rule uses the last recorded attempt status. Whether a retained bundle's `import_reports` and `semantics` still match a fresh import is a consumer responsibility (Evidence Pack, ODES).
