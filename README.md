<!-- cognous-banner:start -->
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

| | |
|---|---|
| Lock status | **selected**: lock key `replay_bundle`, interface Reconstruction Bundle 0.2.0 (see [Selection and compatibility](#selection-and-compatibility)) |
| Stack group | 05 Replay & Evidence (siblings: [Governance Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack), [ODES](https://github.com/cogno-us/open-decision-evidence-standard)); see [where it fits](#cognous-stack-components) |
| Package and command | package `agent-replay-bundle` 0.2.0, import `agent_replay_bundle`, command `arb` ([naming](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/naming.md)) |
| Requirements | Python 3.11 or newer; Linux is the supported platform |
| Documentation | [Documentation index](docs/README.md) |

## What it is, who it is for, what it does not do

**What it is.** A portable reconstruction format, importer, validator and command-line tool for agent-run evidence. Reconstruction Bundle 0.2.0 imports exact supported producer revisions (Control Plane and executor records) while keeping legacy bundle formats and historical provenance distinct. The older replay bundle 0.1 format and its commands remain available for legacy bundles.

**Who it is for.** Engineers who consume Control Plane and executor records and need one connected, source-attributed record of proposals, decisions, attempts, observations and lineage, including uncertainty rather than a retrospective success story; and reviewers who read that record. Engineers can inspect the reference contracts and examples; architecture, security and governance reviewers can examine the boundary and evidence.

**What it does not do.** Reconstruction is non-effecting: it does not rerun a model, reevaluate policy, renew an authorization, repeat an effect, or independently verify delivery. Reconstruction completeness is not destination finality. A valid digest or HMAC is not institutional authority. It is not a security boundary and does not manage keys. The [known limits](#known-limits) are listed below.

**Synthetic example.** A timed-out synthetic refund may have an execution attempt and an unresolved delivery observation. Replay reconstructs those records without converting a missing acknowledgment into settlement or permission to retry. An [Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack) or [ODES](https://github.com/cogno-us/open-decision-evidence-standard) exporter can then derive review material without rerunning the action or rewriting the original records.

## Quick start (about two minutes)

Prerequisites: Python 3.11 or newer, `git`, and network access for package installation (the `pydantic` dependency). Run the commands from the repository root: `arb sign` below writes `signed.json` into the current directory (delete it afterwards).

```bash
git clone https://github.com/cogno-us/cognous-replay-bundle
cd cognous-replay-bundle
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
arb validate examples/customer_service_replay_bundle.json
arb summarize examples/customer_service_replay_bundle.json
arb sign examples/customer_service_replay_bundle.json --secret demo-only-not-a-real-key --key-id demo-key --out signed.json
arb verify signed.json --secret demo-only-not-a-real-key
arb check-examples
```

Expected output:

```text
$ arb validate examples/customer_service_replay_bundle.json
VALID  bundle_id=bundle-cs-001  issues=1
  WARNING W012: signature_metadata is missing.  [signature_metadata]
$ echo $?
0

$ arb summarize examples/customer_service_replay_bundle.json
bundle_id:          bundle-cs-001
run_id:             run-cs-001
status:             complete
...
signed:             no

$ arb sign ... --out signed.json
Signed bundle written to /path/to/signed.json

$ arb verify signed.json --secret demo-only-not-a-real-key
Signature VALID

$ arb check-examples
  OK (reconstruction) bounded_lost_ack_reconstruction_v0_2.json
  OK (reconstruction) bounded_success_reconstruction_v0_2.json
  OK               customer_service_replay_bundle.json
...
  OK (structural)  signed_replay_bundle.json
```

The `W012` warning is expected: the shipped example carries no signature metadata, so the validator says so. It is a warning, not an error, and the exit code stays `0`. Signing it (above) is what adds the metadata. Exit codes: `0` valid; `1` invalid bundle (or `Signature INVALID` for `verify`); `2` file, parse or model error (or a missing command); `3` input outside the size and nesting bounds. `arb --help` lists the six commands.

`demo-only-not-a-real-key` is a placeholder, not a secret. The CLI takes the secret only as an argument, which other local users and shell history can see; use the Python API with a secret from your own secret store where that matters ([signing](docs/signing.md)).

**What this does not prove.** `VALID` means the bundle passed this package's semantic checks. `Signature VALID` means the parsed inner bundle matches what was signed with a shared secret: export integrity only, no signer identity, no key custody ([signing](docs/signing.md)). Neither shows that anything happened at a destination.

To see the manifest, replay and evidence-pack commands run together offline, use `cognous-ocs demo` from the [ergonomics repository](https://github.com/cogno-us/cognous-open-control-stack-ergonomics) (needs network once for installation; its README and `docs/demo.md` state what the demo does and does not prove). For the full selected integration, use the [hub quickstart](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/quickstart.md), whose runner supplies exact producer checkouts and test wiring.

### Run the tests

```bash
python -m pip install -e ".[dev]"
python -m pytest -q tests
```

This runs the component-local tests retained in this repository, which is what the `native` job of the Tests workflow runs. Cross-component test commands run in a disposable checkout assembled by the [qualification workflows](CROSS_COMPONENT_TESTS.md); the migration map there gives the current commands and source identity rules. Historical reports and dependency pins keep their original scope.

## What ships

Status labels: **merged** = merged in this repository; **selected** = pinned in the hub lock; **known limit**; **proposed**. See the [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md#status-labels). A newer commit here is not selected until the hub lock changes. Items marked "after the lock" are not in the revision the lock pins.

### Command-line tool `arb`

| Command | Purpose | Label |
|---|---|---|
| `arb validate <path>` | Validate a replay bundle (0.1 format). A reconstruction bundle is not accepted here; it is loaded through the Python API (`ReconstructionBundle`). | selected |
| `arb summarize <path>` | Print a summary of a replay bundle. | selected |
| `arb redact <path> --out <file> [--targets] [--final-output] [--reasons] [--replacement S] [--policy NAME]` | Write a redacted copy. | selected |
| `arb redact ... [--task] [--scope] [--drop-signature]` | Also redact the task text, scope fields, or drop the embedded signature metadata (all off by default). | merged, after the lock |
| `arb sign <path> --secret <key> --out <file> [--key-id ID]` | Sign a bundle with HMAC-SHA256 (export integrity). | selected |
| `arb verify <path> --secret <key>` | Verify a signed bundle. | selected |
| `arb verify ... --require-bound-envelope` | Refuse a signature that covers the inner bundle only. | merged, after the lock |
| `arb check-examples` | Check every `examples/*.json`: 0.1 bundles are validated; the signed example and the reconstruction examples are checked structurally against their models only. | selected |

### Formats and contracts

| Item | What it is | Label | Details |
|---|---|---|---|
| Reconstruction Bundle 0.2.0 | Evidence-preserving import of recorded producer evidence, with import reports, value states (`absent`, `unknown`, `unavailable`, `redacted`), commitments and loss reporting. | selected | [import contract](docs/reconstruction_import.md), [migration](docs/migration_0_2.md) |
| Replay bundle 0.1 | The legacy format and its validator, redaction and signing. Kept distinct from 0.2.0. | merged; see known limits | [bundle format](docs/bundle_format.md), [validation](docs/validation.md) |
| Executor producer profiles | Versioned executor profile 1.0.0 and 2.0.0 and the legacy unversioned adapter, each tied to exact revisions; unknown revisions are refused, never guessed from shape. | selected | [migration](docs/executor_producer_migration.md), [persistence checkpoint](docs/workstreams/replay-control-plane-persistence-checkpoint.md) |
| Programme-2 opt-in profiles | Run-record members of six opt-in Control Plane profiles (operation identity, rule revision, freshness, merge record, reversibility, dedupe), accepted for one exact Control Plane revision. | merged, after the lock | [profiles](docs/programme-2-profiles.md) |
| Typed refusal, runtime authority and repaired-runtime generations | Separate exact-revision mappings that stay non-selected and additive. | merged, after the lock | [typed refusal](docs/typed-refusal-profile.md), [runtime authority](docs/runtime-authority-profile.md), [repaired runtime](docs/security-runtime-profile-20261016.md), [F5b](docs/security-runtime-f5b-profile-20261016.md) |
| Merged producer compatibility profile | One exact Control Plane and Execution Runtime revision pair for the bounded producer 2.0.0 export (see [below](#merged-producer-compatibility)). | proposed | [profile](docs/workstreams/merged-producer-compatibility.md) |
| W0 C8 compatibility contract | A W0 candidate mapping contract. | merged, after the lock | [contract](docs/w0-c8-compatibility-contract.md) |
| Recovery inspection API 0.1 | Optional, non-effecting inspection of a pinned synthetic recovery export; separate from Reconstruction Bundle 0.2.0. | merged, after the lock | [recovery inspection](docs/recovery-inspection.md) |

### Python modules (`src/agent_replay_bundle/`)

| Module | Purpose |
|---|---|
| `models`, `loader`, `validator` | The 0.1 bundle models, file loader and semantic validator (`validate_replay_bundle`). |
| `reconstruction` | Reconstruction Bundle 0.2.0 models and integrity helpers. |
| `importers` | Importers for Control Plane records (legacy replay, bounded run) and executor exports, by exact producer revision. |
| `redaction`, `signing` | Redaction helpers and HMAC-SHA256 export integrity. |
| `cli` | The `arb` entry point. |
| `ingress`, `instants` | Bounded JSON reading and one strict reader for instants. Merged after the lock. |
| `programme2_profiles` | Programme-2 opt-in profile members. Merged after the lock. |
| `refusal_evidence`, `w3_atomic_import`, `w3_c8_lineage` | Typed refusal evidence and the W3 atomic and C8 lineage reconstructions (non-V1, non-authorizing). Merged after the lock. |
| `recovery_inspection` | Optional recovery inspection. Merged after the lock. |

### JSON schemas (`schemas/`)

| Schema | Describes |
|---|---|
| `agent_replay_bundle.schema.json`, `signed_replay_bundle.schema.json` | The 0.1 bundle and its signed envelope. |
| `reconstruction_bundle_0_2.schema.json` | Reconstruction Bundle 0.2.0. |
| `run_frame`, `action_proposal`, `policy_decision`, `policy_evaluation_trace`, `policy_rule_evaluation`, `blocked_action` | The run frame and its proposal, decision, trace, rule and blocked-action records. |
| `authority_record`, `reliance_record`, `redaction_metadata`, `signature_metadata` | Authority, reliance, redaction and signature records. |
| `validation_report`, `validation_issue` | The validation report and its issues. |

(Each name above is a file `schemas/<name>.schema.json`.)

### Examples (`examples/`)

| File | Shows |
|---|---|
| `customer_service_replay_bundle.json` | A read allowed, an email send blocked, with traces and a reliance record. |
| `internal_research_replay_bundle.json` | Allowed reads and an escalated export. |
| `procurement_replay_bundle.json` | Two blocked actions and an approval gate. |
| `redacted_replay_bundle.json` | A redacted derivative of the customer service bundle. |
| `signed_replay_bundle.json` | The structure of a signed bundle; its signature is a demo placeholder, not a real signature. |
| `bounded_success_reconstruction_v0_2.json`, `bounded_lost_ack_reconstruction_v0_2.json` | Reconstruction Bundle 0.2.0 for a bounded refund that succeeded and one whose acknowledgement was lost. |
| `producer-v2/` | Five producer 2.0.0 captures (success, prior absence, rejected wrong effect, restart, unavailable); not read by `arb check-examples`. |

See [examples](docs/examples.md) for what each bundle demonstrates.

## Documentation

The [documentation index](docs/README.md) lists every page in this repository by role, with historical and generated pages labelled. Start with:

- [Bundle format](docs/bundle_format.md) and [concepts](docs/concepts.md).
- [Reconstruction import contract 0.2.0](docs/reconstruction_import.md), including its [known limitations of legacy and non-V1 paths](docs/reconstruction_import.md#known-limitations-of-legacy-and-non-v1-paths).
- [Signing](docs/signing.md), [redaction](docs/redaction.md) and [validation](docs/validation.md).

For a nontechnical introduction, read the [business overview](collateral/business-collateral.md) and [one-page overview](collateral/one-page-overview.md). Both describe this component's role and evidence limits, not additional runtime features.

## Selection and compatibility

Use the [current component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json) for integration selection and the [central test hub](https://github.com/cogno-us/cognous-stack-qualification/blob/main/results/readme-commentary/index.md) for revision-specific qualification commentary. Source acceptance, selection and deployment approval remain separate decisions.

Producer profile 2.0.0 supports the exact older observation-repair and newer persistence-repair Control Plane revisions documented in the [compatibility checkpoint](docs/workstreams/replay-control-plane-persistence-checkpoint.md). Legacy unversioned and profile-1.0.0 mappings remain separate. Reconstruction Bundle stays 0.2.0.

<!-- pin-round: the lock pin for replay_bundle is 459e4ba62fca; the "after the lock" labels in "What ships" and docs/README.md describe what main adds. Re-read them when the pin moves. -->

Operational deployment trust is still [HOLD under orchestrator #30](https://github.com/cogno-us/cognous-stack-orchestrator/issues/30). No signature, evidence package, successful test or source merge creates a production grant, proves external settlement, or changes selected release authority. Test results and historical qualification records are read against their recorded source revisions.

### Merged producer compatibility

The proposed [merged producer compatibility profile](docs/workstreams/merged-producer-compatibility.md) adds one exact Control Plane/Execution Runtime revision pair for the existing bounded producer 2.0.0 export. Historical pairs remain supported; cross-pair substitutions and unknown revisions remain rejected. The local 19-case qualification uses records generated by the actual merged producers and verifies import does not mutate their stores. Repository CI remains the committed-head acceptance gate.

This is not an atomic-claim or refund-intent evidence importer. New profile-specific exports, downstream consumer adoption and hub pin advancement remain separate.

### Cross component qualification

Executable integration suites and harnesses moved to the [qualification repository](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-replay-bundle). See [the path migration map](CROSS_COMPONENT_TESTS.md) for current commands and source identity rules. Component-local tests remain here; historical qualification results retain their original scope.

<!-- stack-block:start -->
## Where it fits: Cognous stack components

<a id="cognous-stack-components"></a>

The Open Control Stack groups component responsibilities into five groups, plus a cross-cutting exchange and two side groups. The groups are a navigation map. They are not an execution sequence and not a requirement to install every component. Selected revisions come only from the hub [component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json), read with [release status](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md).

| Group | Components |
|---|---|
| 01 Knowledge & Provenance | [Evidence Registry (The Index)](https://github.com/cogno-us/cognous-evidence-registry) · [Evidence Attestation (BitRep)](https://github.com/cogno-us/cognous-evidence-attestation) |
| 02 Institutional Governance | [Institutional Governance (Alvorada)](https://github.com/cogno-us/cognous-institutional-governance) |
| 03 Declaration & Policy Control | [Action Manifest](https://github.com/cogno-us/cognous-action-manifest) · [Control Plane](https://github.com/cogno-us/cognous-control-plane) |
| 04 Constrained Execution | [Execution Runtime](https://github.com/cogno-us/cognous-execution-runtime) |
| 05 Replay & Evidence | [Replay Bundle](https://github.com/cogno-us/cognous-replay-bundle) · [Governance Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack) · [ODES](https://github.com/cogno-us/open-decision-evidence-standard) |
| Cross-cutting exchange | [Governed Exchange (GAX/IMX)](https://github.com/cogno-us/cognous-governed-exchange) |
| Optional reasoning protocols (side group) | [PRP](https://github.com/cogno-us/portable-reasoning-protocol) · [Research Intelligence Protocol](https://github.com/cogno-us/research-intelligence-protocol) · [TFA Protocol](https://github.com/cogno-us/truth-freedom-agency-protocol) |
| Tooling and qualification (side group) | [Ergonomics (cognous-ocs)](https://github.com/cogno-us/cognous-open-control-stack-ergonomics) · [Verifier](https://github.com/cogno-us/cognous-open-control-stack-verifier) · [Orchestrator](https://github.com/cogno-us/cognous-stack-orchestrator) · [Qualification](https://github.com/cogno-us/cognous-stack-qualification) |
| Hub | [Open Control Stack hub](https://github.com/cogno-us/cognous-open-control-stack) |

Hub pages: [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md) (one row per repository), [naming](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/naming.md) (display names, packages, commands, former names), [profiles and tools](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/profiles-and-tools.md) and the [documentation index](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/README.md).

Status labels used in every "What ships" table: **merged** (merged in the owning repository, not by itself selected), **selected** (pinned in the hub lock), **known limit** (a limitation existing documentation already states) and **proposed** (draft or planned, not a supported interface). A signature, registry entry, message receipt or evidence summary does not grant execution authority.

<!-- pin-round: refresh the hub commit on the next line when the component lock changes -->
Last checked against `component-lock.json` at hub commit `dcc9bd7533ef`.
<!-- stack-block:end -->

## Known limits

Each item below is a **known limit** documented in this repository.

- Reconstruction does not reevaluate policy, renew authorization, repeat an effect or independently verify delivery. `reconstruction_complete` means the declared import contract was completely represented, not that an external effect was completed or verified ([import contract](docs/reconstruction_import.md#scope)).
- HMAC signing is export integrity, not key management or non-repudiation. A current signature covers the inner bundle, `signed_bundle_id` and the signature metadata other than the value; an earlier bundle-only signature still verifies and is reported as such, and `--require-bound-envelope` refuses it. Members the models do not retain and the file bytes are not covered. A file signed by this version is not accepted by an earlier version ([signing](docs/signing.md)).
- Redaction replaces only the listed fields; other free text, scope fields (unless `--scope`), the task (unless `--task`) and embedded signature metadata (unless `--drop-signature`) are left as they were, inherited `redacted_fields` are copied unchecked, and a redaction claim is self-asserted ([redaction](docs/redaction.md)). A bundle in which nothing was redacted fails E025.
- The validator's checks are narrow where the docs say so: W011 inspects top-level payload keys only; W013 compares only `checked_id` with `bundle_id`; authority records state what the producer reported and are checked only for `run_id` ([validation](docs/validation.md), [concepts](docs/concepts.md)).
- Legacy 0.1 bundles and the legacy and 1.0.0 executor adapters, and the W3 and C8 mappings, have limits recorded as found, for example that the legacy validator does not reject duplicate identities ([known limitations](docs/reconstruction_import.md#known-limitations-of-legacy-and-non-v1-paths)).
- A completed journal check must match a separately recorded resolution check by stage and inputs, with the journal's reasons a subset of the check's reasons ([runtime authority](docs/runtime-authority-profile.md)). The matcher counts its work against a fixed budget and refuses a run past it with `input_too_large`.
- Without an executor export the import reports finding `B004` (executor and destination evidence absent). A journal observation's destination content is compared only when a proposal is supplied: target, amount, unit, payload, grant and effect are compared with the committed operation; the operation digest is not ([CHANGELOG](CHANGELOG.md)). A journal import never confirms what happened at the destination.
- Review original artifacts and exact source revisions before extending a claim to a new environment. New dependencies, authority sources, destinations or enforcement mechanisms need their own compatibility and qualification. A passing reference case is not a certification of an enterprise deployment.

More shared scope and limits are stated once in the hub [guarantees and limits](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/guarantees-and-limits.md).

## Contributing and attribution

[Contribution guidance](CONTRIBUTING.md) describes review and validation expectations; see also the [security policy](SECURITY.md), the [code of conduct](CODE_OF_CONDUCT.md) and the [changelog](CHANGELOG.md). Keep evidence-linked claims, preserve historical records and separate proposed features from accepted implementation.

See [LICENSE](LICENSE) and [attribution](NOTICE) for the existing terms and third-party scope. Developed by [Cognous](https://cogno.us).

## Repository locations

See the [repository rename map and compatibility notes](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/repository-renames.md) for current component URLs. Existing package names, schema identifiers and retained producer identities are unchanged.

---

## Bibliography

Selected external sources from the October 2026 research review. These inform evaluation questions; they do not establish Cognous implementation, adoption, conformance or production qualification.

- Jonathan Chadbourne / JCEE Labs. *When a Timeout Is Not a Failure: Authority, Evidence, and Recovery in Consequential AI Execution*. Technical Note 001, public release v0.1.1 (6 October 2026). Technical note on uncertain outcomes and recovery. An original public URL has not been verified; no substitute or private copy is linked.
- [Alexander Barrett. *Boundary Blindness Under Artificial Intelligence: Early Cross-Industry Findings on the Missing Decision-Evidence Layer* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7210798). Working paper on carrying the basis for reliance across organizational boundaries; proposed architecture, not a validated interoperability guarantee.
- [Mick Yang et al. *AI Epistemic Risks: Emerging Mechanisms & Evidence* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6873005). Research synthesis on persuasion, cognitive offloading and feedback loops; context for evidence quality and independent judgment.

See the [research bibliography](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/research-bibliography.md) for review scope and source-verification limits.

<!-- Retained anchors for existing documentation links. -->
<a id="current-selection-historical-evidence-and-a-bounded-example"></a>
<a id="evidence-and-supported-scope"></a>
