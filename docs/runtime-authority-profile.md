# Runtime authority candidate mapping

The explicit nonselected mapping pairs Control Plane
`2a17b2ba147462a592d9b1882aad09d8a3eb7904` with runtime
`a9a4f75a9a880ba0ae2c3b5a01fcee0ae904e127`, retaining executor producer 2.0.0
and Reconstruction Bundle 0.2.0. Historical pairings remain unchanged.

Import retains each resolution journal event, purpose read, vocabulary change,
profile binding, refusal vocabulary and read-state field as original committed
source data. Journal validation checks opening, ownership, single closure and
original decision/effect bindings. Each completed journal check must match a
separately recorded resolution check by stage, inputs and reasons; journal and
resolution-check identifiers are distinct producer UUIDs, so the match is by
content, and one resolution check can substantiate at most one completed
journal. Open (never closed) or interrupted checks are retained as evidence of
incompletion: each adds a B006 warning and the reconstruction is
`reconstruction_partial`, never complete. (Imports before this correction did
not lower completeness for such checks.) Reconstruction never grants permission
or dispatches. Refusal capture must match the actual durable refusal supplied by
the executor.

Unsupported fields in typed records reject rather than disappear. Unknown
top-level collections remain explicit B001 losses and cannot yield complete
reconstruction. Downstream `extend_retained_inputs` restores the new collections
before the existing full reconstruction comparison. Replay does not authenticate
producer origin, reverify validator signatures, or independently query delivery.

Cross-component tests belong in cognous-stack-qualification under
`suites/runtime-authority`. Fixtures are original synthetic tests derived from
Moltbook 101526_A K1–K5, 15 October 2026, under the existing Apache-2.0 license.
No selected lock or publication/production hold is changed.
