# Bundle Format

This document describes the structure and fields of the Agent Replay Bundle JSON format.

## Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `bundle_id` | string | yes | Unique identifier for this bundle |
| `bundle_version` | string | no | Format version (default: "0.1"; the validator accepts only `0.1`, error E002) |
| `run_id` | string | yes | Identifier for the agent run |
| `status` | enum | no | "complete", "partial", or "redacted" (default: "complete") |
| `generated_at` | string | yes | ISO 8601 timestamp |
| `producer` | string | no | System that produced the bundle |
| `frame` | object | yes | RunFrame describing the run context |
| `action_proposals` | array | no | List of ActionProposal objects |
| `policy_decisions` | array | no | List of PolicyDecision objects |
| `policy_traces` | array | no | List of PolicyEvaluationTrace objects |
| `blocked_actions` | array | no | List of BlockedAction objects |
| `authority_records` | array | no | List of AuthorityRecord objects |
| `reliance_records` | array | no | List of RelianceRecord objects |
| `final_output` | string | no | The agent's final output |
| `validation_report` | object | no | Embedded ValidationReport |
| `redaction_metadata` | object | no | RedactionMetadata if redacted |
| `signature_metadata` | object | no | SignatureMetadata if signed |
| `metadata` | object | no | Arbitrary additional metadata |

## RunFrame

```json
{
  "frame_id": "frame-001",
  "task": "Description of the task",
  "actor": "agent-name",
  "environment": "production",
  "allowed_tools": ["tool_a", "tool_b"],
  "blocked_tools": ["tool_c"],
  "policy_version": "v1.0",
  "created_at": "2026-01-01T00:00:00Z"
}
```

## ActionProposal

```json
{
  "action_id": "action-001",
  "run_id": "run-001",
  "tool_name": "crm_read",
  "action_type": "read",
  "target": "crm://customers/123",
  "payload": {"customer_id": "123"},
  "proposed_at": "2026-01-01T00:00:01Z",
  "reason": "Need customer data to proceed."
}
```

Action types: `read`, `write`, `external_send`, `delete`, `export`, `purchase`, `approve`, `escalate`, `other`

## PolicyDecision

```json
{
  "decision_id": "decision-001",
  "action_id": "action-001",
  "run_id": "run-001",
  "result": "allow",
  "policy_name": "crm-read-policy",
  "reason": "Agent has crm:read authority.",
  "decided_at": "2026-01-01T00:00:02Z",
  "deterministic_fingerprint": "fp-abc123",
  "trace_id": "trace-001"
}
```

Results: `allow`, `block`, `escalate`

## PolicyEvaluationTrace

```json
{
  "trace_id": "trace-001",
  "run_id": "run-001",
  "action_id": "action-001",
  "evaluated_at": "2026-01-01T00:00:02Z",
  "rules_evaluated": [
    {
      "rule_name": "require-read-authority",
      "matched": true,
      "result": "allow",
      "reason": "Authority record found."
    }
  ],
  "final_result": "allow",
  "deterministic_fingerprint": "fp-abc123"
}
```

The `deterministic_fingerprint` on the trace must match the `deterministic_fingerprint` on the corresponding `PolicyDecision`. The `final_result` must also match.

## BlockedAction

```json
{
  "blocked_id": "blocked-001",
  "action_id": "action-002",
  "run_id": "run-001",
  "reason": "No external_send authority.",
  "policy_name": "external-send-policy",
  "blocked_at": "2026-01-01T00:00:03Z"
}
```

Every `BlockedAction` must correspond to at least one `PolicyDecision` with `result: "block"` for the same `action_id`.

## AuthorityRecord

```json
{
  "authority_id": "auth-001",
  "run_id": "run-001",
  "actor": "agent-name",
  "scope": ["crm:read", "order:read"],
  "source": "service-account-policy",
  "expires_at": "2026-01-01T18:00:00Z",
  "created_at": "2026-01-01T00:00:00Z"
}
```

## RelianceRecord

```json
{
  "reliance_id": "reliance-001",
  "run_id": "run-001",
  "source_name": "crm-service",
  "source_type": "database",
  "scope": "Customer order history",
  "referenced_action_id": "action-001",
  "created_at": "2026-01-01T00:00:03Z"
}
```

Source types: `tool`, `database`, `file`, `api`, `user_input`, `model_output`, `other`

## ID consistency

All `run_id` fields on child objects must equal the top-level `bundle.run_id`. All `action_id` references must point to an existing `ActionProposal.action_id`. All `trace_id` references must point to an existing `PolicyEvaluationTrace.trace_id`.

The validator checks these relationships. See [validation.md](validation.md).
