# Event Taxonomy

This document defines canonical runtime events and minimum fields.

## Common Fields
- `timestamp` (ISO8601)
- `role` (actor)
- `event` (event name)
- `data` (object payload)

## Model/Prompt Lifecycle
1. `turn_start`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `prompt_hash`, `selected_model`
2. `turn_corrective_reprompt`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `reason`
3. `turn_complete`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `duration_ms`, `tool_calls`
4. `turn_non_progress`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `reason`

## Parser Lifecycle
1. `tool_parser_diagnostic`
   - `issue_id`, `session_id`, `turn_index`, `stage`, `details`

## Tool Lifecycle
1. `tool_call_start`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `args`
2. `tool_call_result`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `ok`, `error`
3. `tool_call_exception`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `error`
4. `tool_call_replayed`
   - `issue_id`, `session_id`, `turn_index`, `tool`

## Transition/Failure Lifecycle
1. `retry_triggered`
   - `run_id`, `issue_id`, `retry_count`, `max_retries`, `error`
2. `catastrophic_failure`
   - `run_id`, `issue_id`, `retry_count`, `error`
3. `resume_requeue_issue`
   - `run_id`, `build_id`, `issue_id`, `previous_status`, `new_status`

## Guard Lifecycle
1. `guard_approved`
   - `run_id`, `issue_id`, `seat`, `review_payload`
2. `guard_rejected`
   - `run_id`, `issue_id`, `seat`, `review_payload`
3. `guard_requested_changes`
   - `run_id`, `issue_id`, `seat`, `review_payload`
4. `guard_review_payload`
   - `run_id`, `issue_id`, `payload`
