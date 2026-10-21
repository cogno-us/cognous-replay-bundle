# Validation

This document describes the semantic validation rules applied by `validate_replay_bundle()`.

## Usage

```python
from agent_replay_bundle.loader import load_replay_bundle
from agent_replay_bundle.validator import validate_replay_bundle

bundle = load_replay_bundle("my_bundle.json")
report = validate_replay_bundle(bundle)

if report.valid:
    print("Bundle is valid")
else:
    for issue in report.issues:
        print(f"{issue.severity.value.upper()} {issue.code}: {issue.message}")
```

## Valid vs invalid

A bundle is **valid** (`report.valid = True`) when no error-severity issues are found. Warnings do not affect validity.

## Error rules

| Code | Description |
|---|---|
| E001 | `bundle_id` must be non-empty |
| E002 | `bundle_version` must be non-empty and one of the supported versions (`0.1`) |
| E003 | `run_id` must be non-empty |
| E004 | `frame.frame_id` must be non-empty |
| E005 | `frame.actor` must be non-empty |
| E006 | `frame.policy_version` must be non-empty |
| E007 | Every `ActionProposal.run_id` must equal `bundle.run_id` |
| E008 | Every `PolicyDecision.run_id` must equal `bundle.run_id` |
| E009 | Every `PolicyDecision.action_id` must reference an existing `ActionProposal.action_id` |
| E010 | Every `BlockedAction.run_id` must equal `bundle.run_id` |
| E011 | Every `BlockedAction.action_id` must reference an existing `ActionProposal.action_id` |
| E012 | Every `BlockedAction` must correspond to at least one `PolicyDecision` with `result: "block"` for the same `action_id` |
| E013 | Every `AuthorityRecord.run_id` must equal `bundle.run_id` |
| E014 | Every `RelianceRecord.run_id` must equal `bundle.run_id` |
| E015 | Every `RelianceRecord.referenced_action_id`, when present, must reference an existing `ActionProposal.action_id` |
| E016 | Every `PolicyEvaluationTrace.run_id` must equal `bundle.run_id` |
| E017 | Every `PolicyEvaluationTrace.action_id` must reference an existing `ActionProposal.action_id` |
| E018 | Every `PolicyDecision.trace_id`, when present, must reference an existing `PolicyEvaluationTrace.trace_id` |
| E019 | When `trace_id` is present, the trace `deterministic_fingerprint` must match the decision `deterministic_fingerprint` |
| E020 | When `trace_id` is present, the trace `final_result` must match the decision `result` |
| E021 | Reserved for complete-bundle final-output checks |
| E022 | If `signature_metadata.signed` is true, `signature_algorithm` must be present |
| E023 | If `signature_metadata.signed` is true, `signature` must be present |
| E024 | If `redaction_metadata.redacted` is true, `redacted_at` must be present |
| E025 | If `redaction_metadata.redacted` is true, `redacted_fields` must not be empty |

## Warning rules

| Code | Description |
|---|---|
| W001 | Bundle has no action proposals |
| W002 | Bundle has no policy decisions |
| W003 | Bundle has no policy evaluation traces |
| W004 | Bundle has no reliance records |
| W005 | Bundle has no authority records |
| W006 | `frame.allowed_tools` is empty |
| W007 | `frame.blocked_tools` is empty |
| W008 | An action proposal has no `reason` |
| W009 | A policy decision has no `trace_id` |
| W010 | Bundle status is "complete" but `final_output` is missing |
| W011 | An action payload contains potentially sensitive top-level keys (email, phone, ssn, account_number, customer_id, address, token, secret, password) but `redaction_metadata` is not present; nested keys are not inspected and any `redaction_metadata` suppresses the warning |
| W012 | `signature_metadata` is missing |
| W013 | Embedded `validation_report.checked_id` does not match `bundle_id` |

Complete bundles without `final_output` currently produce warning `W010`, not error `E021`.

## Embedded validation report

A bundle may include an embedded `validation_report`. The validator checks (W013) that `validation_report.checked_id` matches `bundle_id`. W013 flags an embedded report whose `checked_id` differs from `bundle_id`; a different `bundle_version` of the same id, or different issues, is not compared.

The embedded report does not affect the result of `validate_replay_bundle()` — the function always generates a fresh report.

## CLI

```bash
arb validate examples/customer_service_replay_bundle.json
```

Exit codes: `0` = valid, `1` = invalid, `2` = file/parse/model error, `3` = input outside the bounds below.

Duplicate members: a JSON object that repeats a member name is refused by every command and by `load_replay_bundle` (exit code `2`, `duplicate member name`), because the parser would otherwise keep only the last value.

Input bounds: every command reads its file through one bounded reader. A file larger than 32 MiB (`MAX_INPUT_BYTES`) or nested deeper than 128 levels (`MAX_NESTING_DEPTH`) is refused before parsing with the typed error `InputBoundsError` (code `input_too_large` or `nesting_depth_exceeded`) and exit code `3`, which is distinct from the `1` of an invalid bundle.
