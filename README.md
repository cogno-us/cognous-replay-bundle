<!-- cognous-banner:start -->

Cross-component test commands below now run in a disposable checkout assembled by the [qualification workflows](CROSS_COMPONENT_TESTS.md). Plain local test discovery covers the component-local tests retained here. Historical reports and dependency pins keep their original scope.
```text
──────────────────────────────────────────────────
   __________  _______   ______  __  _______
  / ____/ __ \/ ____/ | / / __ \/ / / / ___/
 / /   / / / / / __/  |/ / / / / / / /\__ \
/ /___/ /_/ / /_/ / /|  / /_/ / /_/ /___/ /
\____/\____/\____/_/ |_/\____/\____//____/
              COGNOUS REPLAY BUNDLE
       g o v e r n e d   b y   d e s i g n
  github.com/cogno-us/cognous-open-control-stack
──────────────────────────────────────────────────
```
<!-- cognous-banner:end -->

# Cognous Replay Bundle

**Reconstruct what the retained records support.**

**Stack group: 05 · Replay & Evidence.** See the [six-group component map](#cognous-stack-components).

## Overview

A portable reconstruction format, importer, validator and CLI for agent-run evidence. Reconstruction Bundle 0.2.0 imports exact supported producer revisions while keeping legacy bundle formats and historical provenance distinct.

**Implementation status:** this README describes merged public reference work. Component acceptance, selection in the hub and execution of a qualification are separate facts. The selected revision for this component is `043830b56595cecddfa65c064afd1c0b95e64792`; the [hub lock](https://github.com/cogno-us/cognous-open-control-stack/blob/5737267d94d2b445735c95e8480a31de73a2abe8/component-lock.json) is the source of that integration choice.

## Current selection, historical evidence and a bounded example

**Current selected hub revision:** `459e4ba62fca49364aebb0050cd5fb2dd5a71bfa` ([live component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json)). **Accepted repository source revision:** `2069a0ba1398812c3a8669331a7d8b87c80c4a48`. These are distinct: a newer owning-repository merge or synthetic test is not automatically selected in the hub. The earlier hub checkout `5737267d...` and selected SHA below refer to a **historical evidence generation**, not current selection. Preserve its original counts and limitations. See [hub release status](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md) and [Start here](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/start-here.md).

**Synthetic example:** A timed-out synthetic refund may have an execution attempt and an unresolved delivery observation. Replay reconstructs those records without converting a missing acknowledgment into settlement or permission to retry.

Operational deployment trust is still [HOLD under orchestrator #30](https://github.com/cogno-us/cognous-stack-orchestrator/issues/30). No signature, evidence package, successful test or source merge creates a production grant, proves external settlement, or changes selected release authority.

## Purpose and intended users

Logs from authority evaluation, execution and recovery can disagree or omit important facts. Review requires a connected record of proposals, decisions, attempts, observations and source lineage, including uncertainty rather than a retrospective success story.

Engineers can inspect the reference contracts and examples; enterprise architecture, security and governance reviewers can examine the boundary and evidence. Evaluate this component for its named responsibility rather than as a complete governance platform.

## Key features

| Capability | Implemented or specified responsibility |
|---|---|
| **Producer imports** | Validate exact supported Control Plane and executor combinations; reject unknown revisions rather than guessing compatibility from shape. |
| **Identity continuity** | Preserve proposal, decision and effect identity while keeping Control Plane and executor attempt namespaces separate. |
| **Recovery history** | Retain unknown acknowledgement, rejected/null observations and evidence-only recovery lineage. |
| **Loss and completeness** | Represent declared reconstruction coverage and missing information without claiming effect completion. |
| **Portable review** | Validate, summarize, redact and sign exports; HMAC export integrity is separate from production key management. |

## How it works

After a bounded refund attempt, the importer consumes the actual Control Plane and executor records. It preserves whether the destination was observed applied, absent, partial or unresolved, and which source supplied each fact. An Evidence Pack or ODES exporter can then derive review material without rerunning the action or rewriting the original records.

A valid signature, chain inclusion, message receipt, reasoning instruction or evidence-package digest does not authorize execution. Institutional authority must be supplied and evaluated through the appropriate trusted boundary.

## Getting started

From a fresh repository checkout, use Python 3.11+ and an activated virtual environment. Install only into that environment. Package installation needs network access; the commands below exercise local reference tooling. For the full selected integration, use the [hub quickstart](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/quickstart.md), whose runner supplies exact producer checkouts and test wiring.

```bash
python -m pip install -e ".[dev]"
arb validate examples/customer_service_replay_bundle.json
arb summarize examples/customer_service_replay_bundle.json
arb --help
```

## Evidence and supported scope

The hub selects `043830b56595cecddfa65c064afd1c0b95e64792`. Producer profile 2.0.0 supports the exact older observation-repair and newer persistence-repair Control Plane revisions documented in the [compatibility checkpoint](docs/workstreams/replay-control-plane-persistence-checkpoint.md). Legacy unversioned and profile-1.0.0 mappings remain separate. Reconstruction Bundle stays 0.2.0.

The accepted [hub persistence-generation evidence](https://github.com/cogno-us/cognous-open-control-stack/blob/5737267d94d2b445735c95e8480a31de73a2abe8/examples/control-plane-store-adoption/qualification-summary.json) records 915 Python tests in each of two repetitions, 35 matrix entries satisfying their gates and 120 separate mocked OpenShell tests. Those are aggregate hub results, not a per-component test count or a claim of production readiness. Optional behavioral layers receive static checks only. The [support ledger](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md) separates implementation, execution and adoption.

## Limitations and deployment decisions

Reconstruction is non-effecting. It does not reevaluate policy, renew authorization, repeat an effect or independently verify delivery. Reconstruction completeness is not destination finality. A valid digest or HMAC is not institutional authority; redaction and key custody require deployment-specific controls.

Review original artifacts and their exact source revisions before extending a claim to a new environment. New dependencies, authority sources, destinations or enforcement mechanisms need their own compatibility and qualification. A passing reference case is not a certification of an enterprise deployment.

## Repository guide

Use these sources for details; their historical checkpoints retain the status and scope of the work they recorded:

- [docs/reconstruction_import.md](docs/reconstruction_import.md)
- [docs/executor_producer_migration.md](docs/executor_producer_migration.md)
- [docs/workstreams/replay-control-plane-persistence-checkpoint.md](docs/workstreams/replay-control-plane-persistence-checkpoint.md)
- [docs/signing.md](docs/signing.md)

For a nontechnical introduction, read the [business overview](collateral/business-collateral.md) and [one-page overview](collateral/one-page-overview.md). Both describe this component's role and evidence limits, not additional runtime features.

## Contributing and attribution

[Contribution guidance](CONTRIBUTING.md) describes review and validation expectations. Keep evidence-linked claims, preserve historical records and separate proposed features from accepted implementation.

See [LICENSE](LICENSE) and [attribution](NOTICE) for the existing terms and third-party scope. Developed by [Cognous](https://cogno.us); no licensing change is part of this documentation update.

---

## Bibliography

Selected external sources from the October 2026 research review. These inform evaluation questions; they do not establish Cognous implementation, adoption, conformance or production qualification.

- Jonathan Chadbourne / JCEE Labs. *When a Timeout Is Not a Failure: Authority, Evidence, and Recovery in Consequential AI Execution*. Technical Note 001, public release v0.1.1 (6 October 2026). Technical note on uncertain outcomes and recovery. An original public URL has not been verified; no substitute or private copy is linked.
- [Alexander Barrett. *Boundary Blindness Under Artificial Intelligence: Early Cross-Industry Findings on the Missing Decision-Evidence Layer* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7210798). Working paper on carrying the basis for reliance across organizational boundaries; proposed architecture, not a validated interoperability guarantee.
- [Mick Yang et al. *AI Epistemic Risks: Emerging Mechanisms & Evidence* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6873005). Research synthesis on persuasion, cognitive offloading and feedback loops; context for evidence quality and independent judgment.

See the [research bibliography](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/research-bibliography.md) for review scope and source-verification limits.

## Cognous stack components

The six groups organize component responsibilities. They are not an execution
sequence or a requirement to install every component. The [hub lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json)
defines the selected integration; [release status](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md)
defines its evidence and limits.

| Group | Components |
| --- | --- |
| **01 · Knowledge & Provenance** | [The Index (Evidence Registry)](https://github.com/cogno-us/cognous-evidence-registry) · [BitRep (Evidence Attestation)](https://github.com/cogno-us/cognous-evidence-attestation) |
| **02 · Institutional Governance** | [Alvorada (Institutional Governance)](https://github.com/cogno-us/cognous-institutional-governance) · authority contracts |
| **03 · Declaration & Policy Control** | [Action Manifest](https://github.com/cogno-us/cognous-action-manifest) · [Control Plane](https://github.com/cogno-us/cognous-control-plane) |
| **04 · Constrained Execution** | [Execution Runtime (Moltbot Safe)](https://github.com/cogno-us/cognous-execution-runtime) |
| **05 · Replay & Evidence** | [Replay Bundle](https://github.com/cogno-us/cognous-replay-bundle) · [Governance Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack) · [ODES](https://github.com/cogno-us/open-decision-evidence-standard) |
| **06 · Reasoning & Human Oversight** | [PRP](https://github.com/cogno-us/portable-reasoning-protocol) · [Research Intelligence](https://github.com/cogno-us/research-intelligence-protocol) · [TFA](https://github.com/cogno-us/truth-freedom-agency-protocol) |

**Cross-cutting exchange:** [Governed Exchange (GAX/IMX)](https://github.com/cogno-us/cognous-governed-exchange) connects
governed messages, recipient assessment and continuity across the groups. It is
separate from Alvorada's institutional authority framework.

Execution Runtime and Moltbot Safe name the same repository here. The supported
Cognous Python execution boundary remains distinct from the retained upstream
application. PRP, Research Intelligence and TFA are optional behavioral
instructions; they do not enforce authorization or substitute for human oversight.
A signature, registry entry, message receipt or evidence summary does not grant
execution authority.


## Repository locations

See the [repository rename map and compatibility notes](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/repository-renames.md) for current component URLs. Existing package names, schema identifiers and retained producer identities are unchanged.

## Additional merged producer compatibility

The proposed [merged producer compatibility profile](docs/workstreams/merged-producer-compatibility.md) adds one exact Control Plane/Execution Runtime revision pair for the existing bounded producer 2.0.0 export. Historical pairs remain supported; cross-pair substitutions and unknown revisions remain rejected. The local 19-case qualification uses records generated by the actual merged producers and verifies import does not mutate their stores. Repository CI remains the committed-head acceptance gate.

This is not an atomic-claim or refund-intent evidence importer. New profile-specific exports, downstream consumer adoption and hub pin advancement remain separate.

## Cross component qualification

Executable integration suites and harnesses moved to the [qualification repository](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-replay-bundle). See [the path migration map](CROSS_COMPONENT_TESTS.md) for current commands and source identity rules. Component-local tests remain here; historical qualification results retain their original scope.
