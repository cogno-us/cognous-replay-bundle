# Optional recovery inspection API 0.1

Candidate for Replay issue #22. This native module is separate from Reconstruction Bundle 0.2.0 and the historical bounded-workflow importer. It reads supplied synthetic evidence; it does not open Runtime databases, admit observations, retry effects, reevaluate authority, or contact a destination.

## Exact selection

- Runtime source: `8e7d634cf0a22b6f3c1fc6d93afe92c7414fa243`.
- Producer profile: `cognous-recovery-resolution/synthetic-0.1`.
- Producer export: `cognous-recovery-inspection/synthetic-0.1`.
- Native result: `cognous-replay-recovery-inspection/0.1`.
- Canonicalization: `python-json-sort-ascii-compact/1` (sorted keys, ASCII escaping, compact separators, no NaN; SHA-256 over UTF-8 without a trailing newline).

The repository package version and existing consumer profiles are unchanged. This candidate does not update selected release pins. Selection identifies a contract; it does not authenticate the source repository or caller.

```python
from agent_replay_bundle.recovery_inspection import (
    RUNTIME_REVISION, import_recovery_inspection, validate_recovery_inspection,
)

inspection = import_recovery_inspection(
    runtime_export,
    runtime_revision=RUNTIME_REVISION,
    expected_identity=selected_original_identity,
)
validate_recovery_inspection(inspection)
```

`selected_original_identity` must explicitly contain nonempty `effect_id`, `attempt_id`, `decision_id`, `grant_id`, and `grant_revision`. The caller supplies its independently selected original binding; the importer compares it with retained originals, disposition, receipts, observations, legacy entries, and current projection where applicable. Agreement is consistency, not authentication. A caller copying an untrusted export's identity gains no independent assurance. No tenant or actor is invented.

## Retained source and validation

The entire JSON-compatible input is retained under `source`. No source field is renamed or dropped. Unknown outer, event, envelope, receipt, observation, original/disposition, or legacy field sets are rejected pending explicit profile support. Original and legacy non-identity fields retain their producer values; their real-world truth and all historical v1 semantics are not independently validated.

The importer checks:

- exact profile/export/source selection, required limitations and original in-doubt binding;
- ordered contiguous revisions, unique envelope digests, event/admission identity and receipt policy;
- available envelope digests using the pinned producer serialization, expected revision, and predecessor;
- recorded freshness arithmetic and limits, not freshness at import;
- available observation structure and conflict reasons against prior retained observations;
- permanent conflict HOLD and the current projection derived from the retained sequence;
- explicit legacy provenance gaps and unverified status.

The Runtime export parses its stored JSON before returning it. The importer reproduces the declared canonical serialization for digest comparison; it does not claim receipt of raw database bytes. The separately computed `source_content_sha256` commits the supplied snapshot under the same canonicalization, not its authentic origin.

No-first-observation remains `awaiting_observation`. Unknown/absent does not permit retry. Applied plus complete/final synthetic flags may retain producer `resolved` with `synthetic_profile_only`; the native result still states no execution authority, no independent verification, and no settlement verification.

## Missing payloads and losses

When an event ID was reused with changed content, Runtime can retain only its `conflicting_digest` and `event_id`, plus a receipt. For that entry:

- the original submitted envelope is unavailable;
- submitted-body digest, submitted predecessor and observation-fact checks are not performed;
- the conflict commitment, receipt, revision, original uncertainty and current HOLD are retained;
- no payload is reconstructed from another event or the projection.

`event_checks` distinguishes matched supplied canonical bytes from `not_performed_missing_preimage`. A commitment with no retained preimage is never reported as a verified payload. Full-payload reconstruction remains unavailable if a collision or legacy provenance gap exists. Otherwise the report says only `retained_payloads_only`, not that all real-world evidence is complete.

`loss_report.dropped_fields` is empty for accepted input because the source is retained in full. `unavailable_evidence` lists path-specific producer gaps. Malformed or unsupported input raises `RecoveryInspectionError` instead of returning a misleading success artifact. Revalidating the native result reconstructs all derived findings and requires an exact match, detecting removed loss reports or upgraded assurance labels. This is not a signature: coordinated changes to unauthenticated source and all derived fields are not proof of tampering detectable by this API.

## Qualification

The qualification file is not in this repository; it lives in the qualification repository (see `CROSS_COMPONENT_TESTS.md`). From a checkout of that repository's `suites/cognous-replay-bundle` with Python 3.12, install the existing dev dependencies and provide a checkout of the exact Runtime above:

```bash
COGNOUS_RUNTIME_SOURCE=/absolute/path/to/pinned-runtime python -m pytest -q tests/recovery_inspection_checks.py
```

The qualification file is explicitly selected because it requires the optional external producer fixture. It is not silently skipped when that fixture is missing: the command fails. The dedicated `recovery-inspection.yml` workflow checks out and verifies the Runtime commit and runs this suite. Existing default tests and workflows retain their historical dependency selections.

The suite uses actual Runtime APIs and temporary SQLite stores. It verifies both imported Runtime module blob hashes (normalizing only the terminal newline used in local materialization), checks non-effecting/deterministic copying, unknown/absent/partial/applied states, conflict persistence, exact duplicate after conflict, minimized collision bodies, and legacy gaps. Negative cases cover profile/version, identity, missing original evidence/events, altered digests/predecessors, false current state and assurance, and native loss-report changes. Two disposable mutation controls first pass the same negative test on intact code and then require it to fail with the profile or loss guard removed. Production source is never mutated by those controls.

Local qualification uses fetched source material rather than a full authenticated Git checkout; CI verifies the full producer commit. Neither method proves source authentication, scientific truth, provider finality, complete refusal audit, migration, or production readiness. Evidence Pack mapping and composed orchestrator qualification remain separate tasks. C0 check-to-commit limits, optional same-host C1, no C2/C3, no real settlement and operational trust HOLD remain.
