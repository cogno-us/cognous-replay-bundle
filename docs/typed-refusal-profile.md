# Exact typed refusal candidate profile

This additive, nonselected compatibility mapping accepts CP
`c7f122ba3a6e39f9268a7163c99be3ee514cd97e` only with executor producer 2.0.0
at `63bd4d8d33130de9cc1d3ab3031bd585f2b4e09e` (runtime PR #86; awaiting merge).
This draft pin must be replaced by the actual runtime merge commit before this
PR can be integrated. Historical revision pairings and producer profiles remain
unchanged; arbitrary cross-products are rejected.

Replay preserves refusals, resolution checks, input time floors and attempt
closeouts as committed SourceRecords. It validates their supported typed fields,
original decision/effect/horizon bindings and closeout attempt/accepted-observation
lineage. Actual executor refusal evidence must equal the retained durable record;
missing or substituted evidence is rejected. This checks source consistency, not
a fresh authority evaluation, independent origin authentication or delivery query.
Unknown top-level collections still produce explicit B001 loss and partial status;
unsupported fields inside this typed profile fail closed. No default refusal or
invented authorization reason is supplied. Downstream consumers must reconstruct
all four fields before invoking the unchanged full Replay comparisons.

`typed-refusal.yml` checks exact producer/manifest checkout SHAs and runs sixteen
actual-component cases on Python 3.11/3.12. Six positive scenarios exercise grant,
approval, policy and evidence refusals, successful execution and lost-ack closeout.
Nine negatives reject missing/unknown fields, substituted decision/effect/read
identity, malformed time floors, executor evidence loss/substitution and dangling
closeout. One verifies that unknown top-level data remains explicit loss.
Local sixteen-case run passes with no failures, errors, skips or subtests. Local
legacy run without its pinned integration environment is 184 passes/77 skips;
that is not full historical integration qualification. Existing hosted historical
and merged-producer workflows remain required and retain their original pins.

This profile is preparation for a separate hub candidate and owner selection.
Selected lock/profiles remain unchanged. Publication/production authorization
remains false; operational trust HOLD / NOT ESTABLISHED. C0 check-to-commit limits
and optional same-host cooperative C1 scope remain; no C2/C3 or real settlement.
