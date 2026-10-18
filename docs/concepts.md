# Concepts

This document defines the core concepts in the Agent Replay Bundle format.

---

## AgentReplayBundle

An `AgentReplayBundle` is a portable evidence package for a completed or partially completed AI-agent run. It captures the full governance-relevant record of the run: the task context, every action the agent proposed, every policy decision made, every blocked action, every authority grant in scope, every data source relied upon, and the final output.

A bundle is identified by a `bundle_id` and references a `run_id`. Multiple bundles can reference the same run (for example, original and redacted versions).

---

## RunFrame

A `RunFrame` describes the task context and policy environment for the run. It records:

- The **task** the agent was given
- The **actor** (agent identity)
- The **environment** (production, staging, etc.)
- The **allowed tools** and **blocked tools** for the run
- The **policy version** in effect

The RunFrame is the starting point for understanding what the agent was authorized to do.

---

## ActionProposal

An `ActionProposal` is a single action the agent proposed during the run. It records:

- The **tool** the agent wanted to invoke
- The **action type** (read, write, external_send, delete, export, purchase, approve, escalate, other)
- The **target** resource or endpoint
- The **payload** (parameters the action would send)
- The agent's stated **reason**

Action proposals are the raw record of what the agent wanted to do, before policy evaluation.

---

## PolicyDecision

A `PolicyDecision` is the policy evaluation outcome for a single action proposal. It records:

- The **result**: allow, block, or escalate
- The **policy name** that produced the decision
- The **reason** for the decision
- A **deterministic fingerprint** of the policy inputs
- An optional reference to the detailed `PolicyEvaluationTrace`

Decisions are the authoritative record of what policy allowed, blocked, or escalated.

---

## PolicyRuleEvaluation

A `PolicyRuleEvaluation` is the result of evaluating a single policy rule within a `PolicyEvaluationTrace`. It records the rule name, whether it matched, the result it produced (allow, block, escalate, or none), and the reason.

---

## PolicyEvaluationTrace

A `PolicyEvaluationTrace` provides detailed per-rule evaluation history for an action proposal. It includes the list of `PolicyRuleEvaluation` entries and the final result. The `deterministic_fingerprint` should match the fingerprint on the corresponding `PolicyDecision`.

Traces enable audit review of how a decision was reached.

---

## BlockedAction

A `BlockedAction` is an explicit record that an action proposal was blocked. Every blocked action must correspond to at least one `PolicyDecision` with `result: "block"` for the same `action_id`.

Blocked actions are first-class records, separate from the policy decision, to make them easy to enumerate in audit review.

---

## AuthorityRecord

An `AuthorityRecord` records an authority grant in scope for the run. It captures:

- The **actor** holding the authority
- The **scope** (list of permissions or capabilities)
- The **source** of the authority (user delegation, system policy, etc.)
- Optional expiry

Authority records state the authority the producer reported; the validator checks only their `run_id` and nothing binds them to decisions or proposals, so a reviewer cannot verify from them alone that the agent had (or lacked) the authority needed for proposed actions.

---

## RelianceRecord

A `RelianceRecord` records a data source the agent relied on during the run. It captures:

- The **source name** and **source type** (tool, database, file, api, user_input, model_output, other)
- The **scope** of reliance
- An optional reference to the action that triggered it

Reliance records enable reviewers to understand what information the agent based its decisions and outputs on.

---

## ValidationReport

A `ValidationReport` is the result of running semantic validation on a bundle. It contains a `valid` flag (true only when no error-severity issues are present) and a list of `ValidationIssue` entries with stable code strings, severity levels, messages, and optional field paths.

---

## RedactionMetadata

`RedactionMetadata` records what was redacted from a bundle, when, under what policy, and with what replacement string. It lists the field paths that were redacted. The presence of `RedactionMetadata` with `redacted: true` records a redaction claim; it is self-asserted and does not show which content was actually removed.

---

## SignatureMetadata

`SignatureMetadata` records an export integrity signature applied to a bundle. It captures the algorithm, the hex-encoded signature, the signing timestamp, and an optional key identifier.

HMAC-SHA256 signing is export integrity, not production key management. See [signing.md](signing.md).

---

## SignedReplayBundle

A `SignedReplayBundle` is a wrapper that pairs a `AgentReplayBundle` with its `SignatureMetadata`. The signature covers the canonical serialization of the bundle (with sorted keys, compact separators, and the signature field excluded).
