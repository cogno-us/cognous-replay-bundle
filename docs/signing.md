# Signing

This document describes the export integrity signing provided by Agent Replay Bundle.

## Purpose

Signing a 0.1 replay bundle provides limited **export integrity**: a holder of the same shared secret can check that the model-dumped inner `replay_bundle` (the canonical form below) still matches the HMAC. This is useful for sharing bundles across systems, storing them in audit logs, or attaching them to incident reports.

It is not a record that the received JSON file is unmodified. Verification first parses the file through the Pydantic models and then recomputes the HMAC over `model_dump`. Properties those models do not retain can be added to the file and are not authenticated.

**Two signature forms.** A signature written by the current version covers the whole parsed inner `replay_bundle` (including its own embedded `signature_metadata`), `signed_bundle_id`, and the outer `signature_metadata` fields other than the signature value (`signed`, `signed_at`, `signature_algorithm`, `key_id`); changing any of them fails verification. A signature written by an earlier version (bundle only) still verifies: the outer envelope of such a file, `signed_bundle_id` and those `signature_metadata` fields, can be changed without failing verification. `signature_coverage()` returns `"envelope_and_bundle"`, `"bundle_only"` or `None` for the form that matched. `arb verify` prints a note on stderr for a bundle-only signature and `--require-bound-envelope` (API: `allow_unbound_envelope=False`) refuses it; re-sign the bundle to get the current form. A file signed by the current version is not verified by an earlier version of this package.

`verify` refuses a file in which any JSON object repeats a member name (exit code 2, `Invalid JSON`); a parser would otherwise keep only the last value, so what is checked would differ from what a reader of the file sees. Loading a bundle for `validate` and the other commands keeps the parser's last-value behaviour, as before. `verify` also applies the input bounds of `docs/validation.md` (byte budget and nesting depth, exit code 3).

Summary of what the HMAC covers: for a current signature, the canonical form of the parsed inner `replay_bundle`, `signed_bundle_id` and the `signature_metadata` fields other than the value being checked; for a bundle-only signature, only the canonical form of the parsed inner `replay_bundle`. Neither covers members the models do not retain, or the file bytes.

## Algorithm

Agent Replay Bundle uses **HMAC-SHA256** with a caller-supplied secret.

## Limitation

**This is export integrity, not production key management.**

HMAC-SHA256 with a shared secret does not provide:
- Non-repudiation (the signer's identity is not proven)
- Protection against compromise of the signing secret
- A PKI-based trust hierarchy

For high-assurance production use cases, use a proper key management system and consider asymmetric signing (e.g., Ed25519 or RSA-PSS with an HSM or KMS).

The CLI takes the secret only as a `--secret` argument. Command-line arguments can be visible to other local users and processes and may be kept in shell history or command logs. Use the Python API with a secret obtained from a deployment-specific secret store where that exposure matters.

## Usage

### Signing

```python
from agent_replay_bundle.loader import load_replay_bundle
from agent_replay_bundle.signing import sign_replay_bundle

bundle = load_replay_bundle("my_bundle.json")
signed = sign_replay_bundle(bundle, secret="my-secret", key_id="key-001")

import json
with open("signed.json", "w") as f:
    json.dump(signed.model_dump(mode="json"), f, indent=2)
```

### Verification

```python
import json
from agent_replay_bundle.models import SignedReplayBundle
from agent_replay_bundle.signing import verify_signed_replay_bundle

with open("signed.json") as f:
    data = json.load(f)

signed = SignedReplayBundle.model_validate(data)
is_valid = verify_signed_replay_bundle(signed, secret="my-secret")
print("Valid" if is_valid else "Invalid")
```

### CLI

```bash
arb sign examples/customer_service_replay_bundle.json \
    --secret "my-secret" \
    --out /tmp/signed.json \
    --key-id "key-001"

arb verify /tmp/signed.json --secret "my-secret"
```

## Canonical serialization

The bundle-only form (still accepted for earlier signatures) is produced by:

1. Calling `bundle.model_dump(mode="json")`
2. Removing the entire `signature_metadata` field from the `AgentReplayBundle` payload
3. Serializing with `sort_keys=True`, compact separators `(",", ":")`, and `ensure_ascii=True`

The bundle-only form is stable: the same bundle will always produce the same canonical string when all non-signature fields match, regardless of any embedded `signature_metadata`.

The current form signs the bytes `agent-replay-bundle/export-signature/2\n` followed by one canonical JSON document (same sorting, separators and ASCII escaping) with the members `signed_bundle_id`, `signature_metadata` (without `signature`) and `replay_bundle` (the full `model_dump`, embedded `signature_metadata` included). The prefix keeps the two forms apart.

## SignatureMetadata

After signing, the bundle's `signature_metadata` is populated with:

```json
{
  "signed": true,
  "signed_at": "2026-07-01T12:00:00Z",
  "signature_algorithm": "HMAC-SHA256",
  "signature": "<hex digest>",
  "key_id": "key-001"
}
```

## SignedReplayBundle

The output of signing is a `SignedReplayBundle`:

```json
{
  "signed_bundle_id": "signed-bundle-cs-001-abcd1234",
  "replay_bundle": { ... },
  "signature_metadata": { ... }
}
```

`SignedReplayBundle.signature_metadata` is where signed exports carry their signature value. For a current signature the remaining fields and `signed_bundle_id` are covered by it; for a bundle-only signature they are unauthenticated, caller-supplied labels and must not be relied on as signing time, algorithm or key identity. The HMAC is still a shared-secret check: `key_id` is a label that a verifier looks up, not proof of key identity.

`AgentReplayBundle.signature_metadata` is optional embedded metadata for systems that store signature state directly on the bundle. It is not part of the bundle-only canonical form; a current signature covers it as part of the inner bundle.
