# Changelog

## Unreleased

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
