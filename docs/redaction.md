# Redaction

This document describes how redaction works in Agent Replay Bundle.

## Purpose

Redaction replaces only the fields listed under "What can be redacted" (proposal payload, target and reason, decision, rule and blocked-action reasons, final output, and, when the options are set, task, scope and the embedded signature metadata). Other free text in `frame`, reliance and authority records and other embedded metadata is not redacted, and inherited `redacted_fields` entries are copied unchecked. A redacted bundle retains enough governance-relevant structure to support audit review, incident reconstruction, and policy verification.

## What is preserved

Redaction **always preserves**:

- All IDs (`bundle_id`, `run_id`, `action_id`, `decision_id`, `trace_id`, etc.)
- All timestamps
- Decision results (allow, block, escalate)
- Policy names
- Deterministic fingerprints
- Trace relationships
- Action references

These fields are essential for governance review and must not be removed.

## What can be redacted

| Option | Default | Replaces |
|---|---|---|
| `redact_payloads` | `True` | `ActionProposal.payload` → `{"redacted": true}` |
| `redact_targets` | `False` | `ActionProposal.target` → replacement string |
| `redact_final_output` | `False` | `final_output` → replacement string |
| `redact_reasons` | `False` | `ActionProposal.reason`, `PolicyDecision.reason`, `PolicyRuleEvaluation.reason`, `BlockedAction.reason` → replacement string |
| `redact_task` | `False` | `RunFrame.task` → replacement string |
| `redact_scope` | `False` | `RelianceRecord.scope` → replacement string; each `AuthorityRecord.scope` list → a one-item list holding the replacement |
| `clear_signature_metadata` | `False` | the embedded `signature_metadata` is dropped (it describes a signature over the content before redaction) |

With the defaults, the task text, the scope fields and any embedded `signature_metadata` are left as they were: a redacted bundle can still show the original task, the scope of each reliance and authority record, and `signed: true` with a signature over the earlier content. Turn the three options on (CLI: `--task`, `--scope`, `--drop-signature`) when those must not leave with the bundle, and re-sign the derivative if a signature is needed.

## Usage

```python
from agent_replay_bundle.loader import load_replay_bundle, dump_replay_bundle
from agent_replay_bundle.redaction import redact_replay_bundle

bundle = load_replay_bundle("original.json")

redacted = redact_replay_bundle(
    bundle,
    redact_payloads=True,
    redact_targets=True,
    redact_final_output=True,
    redact_reasons=False,
    redact_task=False,
    redact_scope=False,
    clear_signature_metadata=False,
    replacement="[REDACTED]",
    redaction_policy="public-review",
)

dump_replay_bundle(redacted, "redacted.json")
```

## CLI

```bash
arb redact examples/customer_service_replay_bundle.json \
    --out /tmp/redacted.json \
    --targets \
    --final-output \
    --policy "public-review"
```

## Behavior

- `redact_replay_bundle()` returns a **deep copy**. The original bundle is not mutated.
- The bundle `status` is set to `"redacted"`.
- `RedactionMetadata` is created (or updated) with `redacted: true`, the current UTC timestamp, the list of redacted field paths, and the redaction policy.
- Deterministic fingerprints are **not recomputed** after redaction. This is intentional: the fingerprints should match the original policy inputs. A reviewer comparing a redacted bundle against policy logs will see matching fingerprints.

## Field paths in redaction_metadata.redacted_fields

The `redacted_fields` list records the dot-path to each redacted field. Example:

```json
"redacted_fields": [
  "action_proposals[0].payload",
  "action_proposals[1].payload",
  "action_proposals[0].target",
  "final_output"
]
```

## Validation of redacted bundles

The validator (rule E024, E025) checks that if `redaction_metadata.redacted` is true, then `redacted_at` is present and `redacted_fields` is non-empty. A redacted bundle validates without errors unless no field was redacted (for example a bundle with no proposals, decisions or traces): the legacy helper still sets `redacted: true` with an empty `redacted_fields`, which fails E025.
