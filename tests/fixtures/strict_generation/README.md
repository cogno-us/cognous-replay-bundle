# strict_generation fixtures (Replay-2)

Real Control Plane records, produced by `generate_from_cp.py` against cogno-us/cognous-control-plane PR #109 (CP-2) head
`5bff525a8e08139e02873b409053830f42969006` (a tenant-aware `BoundedAuthorizationWorkflow` decision persisted through the Control Plane's own `BoundedRecordStore`),
one per tenant-binding generation. Nothing in them is hand edited; the tests mutate deep copies only. Synthetic data.

`vectors.json` is the shared identity vector: for each generation, `proposal`, `grant_id`, `grant_revision`, `generation`, the Control Plane `_effect_id`
(`control_plane_effect_id`) and the effect id Replay expects (`expected_effect_id`); they are equal by construction and asserted equal by
`tests/test_strict_effect_identity.py`.

    legacy  = sha256_canonical({"proposal", "grant_id", "grant_revision"})
    strict  = sha256_canonical({"proposal", "grant_id", "grant_revision", "tenant_generation": "bounded-authorization-effect/0.3-strict-tenant"})
