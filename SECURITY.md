# Security Policy

## Scope

Agent Replay Bundle is a schema, validator, redaction helper, and signing helper for AI-agent run records. It is not a security boundary, runtime access control system, or policy enforcement engine.

## What this library does

- Defines a portable JSON format for AI-agent run evidence
- Validates bundle consistency
- Replaces the listed fields of a bundle (see docs/redaction.md); other free text, scope fields and embedded signature metadata are left as they were unless the matching options are set
- Signs bundles with HMAC-SHA256 for export integrity

## What this library does not do

- It does not enforce runtime access control
- It does not authenticate users or agents
- It does not provide key management
- It does not store or transmit data

## HMAC signing

HMAC-SHA256 signing in this library is **export integrity**, not production key management. The signature checks that the parsed inner `replay_bundle` matches what was signed with a given secret; a signature written by the current version also covers `signed_bundle_id` and the outer signature fields other than the value, while a bundle-only signature written by an earlier version leaves those envelope fields uncovered, and members the models do not retain and the file bytes are not covered (see docs/signing.md). It does not:

- Provide non-repudiation
- Authenticate the signer's identity
- Protect against compromise of the signing secret
- Replace a proper PKI or HSM-based signing solution for high-assurance use cases

Use appropriate key management practices for your environment.

## Redaction

Redaction must be configured correctly for your use case. The library provides a reference implementation. You are responsible for:

- Selecting the appropriate redaction profile for your export target
- Verifying that required fields are redacted before sharing bundles externally
- Testing redaction output against your data classification requirements

## Operational security

Use this library alongside:

- Application-level authorization controls
- Runtime policy gates
- Logging and monitoring
- Secure secret management
- Operational security controls appropriate for your environment

## Reporting a vulnerability

If you discover a security vulnerability in this repository, please open a GitHub issue with the label `security` or contact the maintainers directly. Do not include sensitive data in public issue reports.
