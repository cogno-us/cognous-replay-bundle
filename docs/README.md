# Documentation index: Cognous Replay Bundle

Every documentation page in this repository, by purpose. Historical, generated and candidate pages are labelled rather than hidden: they stay valid for the revision or plan they describe and do not describe the current selection. Back to the [repository README](../README.md).

Labels follow the hub [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md#status-labels): **merged**, **selected**, **known limit**, **proposed**. Names are explained in the hub [naming table](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/naming.md).

## Start by role

| Your role | First page | Then |
|---|---|---|
| New reader | [Concepts](concepts.md) | [Bundle format](bundle_format.md), [examples](examples.md) |
| Using the `arb` command | [README quick start](../README.md#quick-start-about-two-minutes) | [Validation](validation.md), [signing](signing.md), [redaction](redaction.md) |
| Importing producer records | [Reconstruction import contract 0.2.0](reconstruction_import.md) | [Executor producer migration](executor_producer_migration.md), [migration to 0.2.0](migration_0_2.md), [Programme-2 profiles](programme-2-profiles.md) |
| Reviewer judging what a bundle shows | [Reconstruction import: scope](reconstruction_import.md#scope) | [Known limitations](reconstruction_import.md#known-limitations-of-legacy-and-non-v1-paths), [README known limits](../README.md#known-limits) |
| Checking producer compatibility | [Persistence checkpoint](workstreams/replay-control-plane-persistence-checkpoint.md) | [Merged producer compatibility](workstreams/merged-producer-compatibility.md), [W3 compatibility checkpoint](workstreams/w3-evidence-compatibility.md) |
| Contributor | [CONTRIBUTING](../CONTRIBUTING.md) | [Cross-component tests](../CROSS_COMPONENT_TESTS.md), [changelog](../CHANGELOG.md) |

## Current pages

| Page | What it covers | Label |
|---|---|---|
| [Concepts](concepts.md) | The core concepts of the 0.1 bundle: frame, proposal, decision, trace, blocked action, authority, reliance, redaction, signature. | merged |
| [Bundle format](bundle_format.md) | Every field of the 0.1 replay bundle and its ID consistency rules. | merged |
| [Validation](validation.md) | The semantic rules (errors and warnings), the embedded report, CLI exit codes and input bounds. | merged |
| [Redaction](redaction.md) | What can be redacted, what is preserved, and what redaction does not cover. | merged |
| [Signing](signing.md) | HMAC-SHA256 export integrity: what a signature covers, bundle-only signatures, and its limits. | merged |
| [Reconstruction import contract 0.2.0](reconstruction_import.md) | The 0.2.0 import contract: scope, supported producer profiles, import reports and value states, commitments, integrity, evidence classes, known limitations. | selected |
| [Migration to reconstruction bundle 0.2.0](migration_0_2.md) | Why 0.2.0 is a separate model, the migration paths, and unsupported producer revisions. | selected |
| [Executor producer migration](executor_producer_migration.md) | Versioned executor producer profiles, the legacy unversioned adapter, attempt namespaces and lifecycle shapes. | selected |
| [Examples](examples.md) | What each example bundle demonstrates. | merged |
| [Integration with the Control Plane](integration_with_agent_control_plane.md) | The conceptual relationship between Replay Bundle and the Control Plane. | merged |
| [Programme-2 opt-in profiles](programme-2-profiles.md) | The run-record members of six opt-in Control Plane profiles, accepted for one exact revision, and the reason-registry labels. | merged |
| [Optional recovery inspection API 0.1](recovery-inspection.md) | A candidate, non-effecting inspection of a pinned synthetic recovery export. Its test file lives in the qualification repository. | merged |

## Candidate mappings and producer generations

Each page below describes an additive, exact-revision mapping that is not selected by the hub lock. They are kept so the revisions they name stay attributable.

| Page | What it covers | Label |
|---|---|---|
| [Typed refusal candidate profile](typed-refusal-profile.md) | One exact Control Plane revision with executor producer 2.0.0 for typed effect-time refusal evidence. | merged |
| [Runtime authority candidate mapping](runtime-authority-profile.md) | A nonselected mapping for runtime-authority journals, with how journal checks match recorded resolution checks. | merged |
| [Repaired runtime generation (16 October 2026)](security-runtime-profile-20261016.md) | One exact Control Plane and executor generation with a Manifest attribution. | merged |
| [F5b repaired runtime generation (16 October 2026)](security-runtime-f5b-profile-20261016.md) | A further exact generation beside the other generations. | merged |
| [W0 C8 compatibility contract](w0-c8-compatibility-contract.md) | A W0 candidate mapping contract for evidence compatibility. | merged |
| [Merged producer compatibility](workstreams/merged-producer-compatibility.md) | One exact Control Plane and Execution Runtime revision pair for the bounded producer 2.0.0 export. | proposed |

## Generated, checkpoint and planning pages

| Page | What it is | Label |
|---|---|---|
| [Contract conformance: execution-attempt-lifecycle (consumer)](contract-conformance-execution-attempt-lifecycle.md) | Generated table of the consumer conformance outcomes. A test checks that it is current: regenerate it, do not edit it by hand. | generated |
| [Persistence checkpoint](workstreams/replay-control-plane-persistence-checkpoint.md) | Compatibility checkpoint for the Control Plane persistence repair. | historical |
| [Producer 2.0.0 checkpoint](workstreams/replay-producer-v2-checkpoint.md) and [scenario results](workstreams/producer_v2_results.json) | Checkpoint of the Replay change for executor producer 2.0.0, with machine-readable scenario results. | historical |
| [W3 compatibility checkpoint](workstreams/w3-evidence-compatibility.md) | Replay and Evidence compatibility checkpoint, with the revisions it was prepared against. | historical |
| [Roadmap](roadmap.md) | Planned and potential future work. Items are plans, not features. | proposed |
| [Changelog](../CHANGELOG.md) | Unreleased changes and earlier notes, newest first. | merged |

## Other files

- [README](../README.md): what it is, quick start, what ships, known limits.
- [SECURITY](../SECURITY.md): scope of the library and how to report an issue.
- [CONTRIBUTING](../CONTRIBUTING.md), [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md), [LICENSE](../LICENSE), [NOTICE](../NOTICE).
- [Cross-component tests](../CROSS_COMPONENT_TESTS.md): where the integration suites live and how the workflows call them.
- [Business overview](../collateral/business-collateral.md) and [one-page overview](../collateral/one-page-overview.md): nontechnical introductions. They describe this component's role and evidence limits, not additional features.
- [`tests/contracts/execution-attempt-lifecycle/README.md`](../tests/contracts/execution-attempt-lifecycle/README.md): a vendored copy of the lifecycle contract README used by the conformance tests. It is checked for drift and is not edited here.
