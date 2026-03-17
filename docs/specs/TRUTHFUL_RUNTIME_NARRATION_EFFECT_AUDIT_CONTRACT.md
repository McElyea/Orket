# Truthful Runtime Narration-Effect Audit Contract

Last updated: 2026-03-16
Status: Active
Owner: Orket Core
Phase closeout authority: `docs/projects/archive/truthful-runtime/TRH03162026-PHASE-C-CLOSEOUT/CLOSEOUT.md`
Related authority:
1. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md`
2. `docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md`

## Purpose

Define the durable packet-2 audit contract that verifies narrated tool effects against runtime-owned evidence instead of trusting narration alone.

## Current Scope

This contract currently covers successful narrated effects from:
1. `write_file`
2. `update_issue_status`

Truth source priority:
1. successful protocol receipts
2. legacy per-turn `parsed_tool_calls.json` plus matching `tool_result_*.json` artifacts when protocol receipts are absent

Out of scope:
1. semantic correctness of file contents
2. remote side effects outside workspace artifacts or card history
3. voice, avatar, or publication-side effect verification

## Canonical Surface

Packet-2 additive key:
1. `truthful_runtime_packet2.narration_to_effect_audit`

Minimum emitted shape:

```json
{
  "audit_occurred": true,
  "verified_count": 2,
  "missing_effect_count": 0,
  "entries": [
    {
      "operation_id": "<operation_id>",
      "tool": "write_file",
      "effect_target": "agent_output/main.py",
      "audit_status": "verified",
      "failure_reason": "none"
    }
  ]
}
```

## Entry Rules

Required fields per entry:
1. `operation_id`
2. `tool`
3. `effect_target`
4. `audit_status`
5. `failure_reason`

Optional additive fields:
1. `issue_id`
2. `role_name`
3. `turn_index`
4. `step_id`

Stable `audit_status` values:
1. `verified`
2. `missing`

Stable `failure_reason` values:
1. `none`
2. `artifact_path_missing`
3. `artifact_path_outside_workspace`
4. `workspace_artifact_missing`
5. `card_status_target_missing`
6. `card_status_transition_missing`

## Verification Rules

For `write_file`:
1. the receipt must report `execution_result.ok = true`
2. the target path must resolve inside the workspace
3. the resolved target must exist as a file at finalize time
4. failures must use:
   1. `artifact_path_missing` when no path is attributable
   2. `artifact_path_outside_workspace` when the resolved path escapes the workspace
   3. `workspace_artifact_missing` when narration claims success but no artifact exists

For `update_issue_status`:
1. the receipt must report `execution_result.ok = true`
2. the audit target is `<issue_id>:<status>`
3. verification uses authoritative card history, not narration text
4. failures must use:
   1. `card_status_target_missing` when issue or status cannot be resolved
   2. `card_status_transition_missing` when the target transition is absent from card history

## Emission Rules

1. Omit `narration_to_effect_audit` when no qualifying successful narrated effects were observed.
2. When emitted, `audit_occurred` must be `true`.
3. `verified_count` must equal the number of `entries` with `audit_status = verified`.
4. `missing_effect_count` must equal the number of `entries` with `audit_status = missing`.
5. Packet-2 narration/effect audit is additive and must not silently change terminal run status by itself.

## Live Evidence Authority

1. Provider-backed suite: `tests/live/test_truthful_runtime_phase_c_completion_live.py`
2. Structural integration coverage: `tests/application/test_execution_pipeline_run_ledger.py`
