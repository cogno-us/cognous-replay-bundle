# Runtime authority candidate mapping

The explicit nonselected mapping pairs Control Plane
`7aa98ac452de4619161bef177cdd9c07fc606f03` with runtime
`12a54405efc627c9025542c5d45be80526a8adee`, retaining executor producer 2.0.0
and Reconstruction Bundle 0.2.0. Historical pairings remain unchanged.

Import retains each resolution journal event, purpose read, vocabulary change,
profile binding, refusal vocabulary and read-state field as original committed
source data. Journal validation checks opening, ownership, terminality and
original decision/effect bindings. Open or interrupted checks remain evidence of
incompletion; reconstruction never grants permission or dispatches. Refusal
capture must match the actual durable refusal supplied by the executor.

Unsupported fields in typed records reject rather than disappear. Unknown
top-level collections remain explicit B001 losses and cannot yield complete
reconstruction. Downstream `extend_retained_inputs` restores the new collections
before the existing full reconstruction comparison. Replay does not authenticate
producer origin, reverify validator signatures, or independently query delivery.

Cross-component tests belong in cognous-stack-qualification under
`suites/runtime-authority`. Fixtures are original synthetic tests derived from
Moltbook 101526_A K1–K5, 15 October 2026, under the existing Apache-2.0 license.
No selected lock or publication/production hold is changed.
