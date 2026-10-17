# F5b repaired runtime producer generation (16 October 2026)

This change adds another exact generation, kept separate from the others: Control Plane `a34c3dc26f84a767a55f9d5c89dc0b53e63fefa5`, executor `4a83b175d2ef0e65a7ee22a0513bb94a5fdf3a6f` and Manifest `2c36bcd0b620dbfe7ad924bc7196a3f0c04c5c5e`. Its profiles are `control-plane-security-runtime@a34c3dc2` and `moltbot-safe-executor-producer-2.0.0@4a83b175`. These are the merged revisions after the F5b security repairs.

The change follows the same additive pattern as the [repaired runtime generation](security-runtime-profile-20261016.md). It does not change the earlier CP `996baeb4` / executor `fd6b76fa` / Manifest `e385f8c1` generation, the other historical mappings or the producer pairing restrictions, so retained evidence from those generations still imports. Each pairing is exact and one-to-one: Replay rejects any executor/Control Plane combination that mixes revisions from different generations.

The producers' exported data contract has not changed since the previous generation. The F5b changes do the following:
- Control Plane fails closed on tenant-bearing authority state that is used with a tenant-less proposal.
- Control Plane rejects non-finite claim amounts and refuses unsafe persistence identifiers.
- The runtime validates the construction of the local execution policy and audits malformed actions.

The new generation applies the same import semantics as the previous one: runtime-authority journals and vocabulary, typed refusals, the bounded `failure_record_id` reference labelled `source_asserted_not_independently_verified`, and strict acknowledgement and semantic validation.

Cross-component cases and results belong to `cognous-stack-qualification/suites/security-runtime`. This mapping is a candidate component revision. It needs F3 requalification, refreeze and re-review before anyone accepts it. It does not select a profile and does not authorize a release or production use. C0 and deployment limits remain.
