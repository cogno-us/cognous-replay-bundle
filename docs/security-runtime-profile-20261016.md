# Repaired runtime producer generation — 16 October 2026

Adds a separate exact CP `996baeb476c8745b1a58ddc968b9eecc6a39b76b` / executor `fd6b76fa0e85feb5b67324114bf790d3a12fdaf1` generation and Manifest `e385f8c19b4444817a8b84b72ed6edbc37deb807` attribution. Historical mappings and producer pair restrictions remain unchanged. CP source under `src/` is byte-identical to the prior runtime-authority revision; the runtime includes the merged security repairs.

The new generation retains runtime-authority fields, journals, vocabulary changes, typed refusals and existing strict semantic validation. Hardened executor denial evidence includes `failure_record_id`; it is retained only as a bounded nonempty source-asserted reference on a nonattempted denial. The producer does not export the referenced failure row, so Replay explicitly labels its verification as `source_asserted_not_independently_verified`. This reference cannot establish independent durability or permission. The actual durable refusal and execution/decision bindings remain required and checked independently of that reference.

Cross-component cases and results belong to `cognous-stack-qualification/suites/security-runtime` and its result records. No selected profile or release/production authorization changes. C0 and deployment limits remain.
