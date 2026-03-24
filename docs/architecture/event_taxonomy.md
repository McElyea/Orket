# Event Taxonomy

This document defines canonical runtime events and minimum fields.

## Common Fields
- `timestamp` (ISO8601)
- `role` (actor)
- `event` (event name)
- `data` (object payload)

## Model/Prompt Lifecycle
1. `turn_start`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `prompt_hash`, `selected_model`, `execution_profile`, `builder_seat_choice`, `reviewer_seat_choice`, `seat_coercion`, `artifact_contract`, `odr_active`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`
2. `turn_corrective_reprompt`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `reason`, `contract_reasons`
3. `turn_complete`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `duration_ms`, `tool_calls`, `execution_profile`, `builder_seat_choice`, `reviewer_seat_choice`, `seat_coercion`, `artifact_contract`, `odr_active`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`
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
5. `determinism_violation`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `error`, `error_code`, `determinism_class`, `capability_profile`, `tool_contract_version`, `side_effect_signal_keys`

`determinism_violation` is emitted to the runtime event artifact stream at `agent_output/observability/runtime_events.jsonl` when a tool's observed side effects contradict its declared determinism class.

## Transition/Failure Lifecycle
1. `retry_triggered`
   - `run_id`, `issue_id`, `retry_count`, `max_retries`, `error`
2. `catastrophic_failure`
   - `run_id`, `issue_id`, `retry_count`, `error`
3. `resume_requeue_issue`
   - `run_id`, `build_id`, `issue_id`, `previous_status`, `new_status`
4. `packet1_fact`
   - `session_id`, `packet1_facts`
5. `packet1_emission_failure`
   - `run_id`, `session_id`, `stage`, `error_type`, `error`, `packet1_conformance`
6. `packet2_fact`
   - `session_id`, `packet2_facts`
7. `artifact_provenance_fact`
   - `session_id`, `artifact_provenance_facts`
8. `turn_failed`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `type`, `error`
9. `odr_prebuild_completed`
   - `session_id`, `issue_id`, `execution_profile`, `odr_active`, `selected_model`, `odr_run_id`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`, `odr_requirement`, `odr_rounds_completed`, `odr_accepted`
10. `odr_prebuild_failed`
   - `session_id`, `issue_id`, `execution_profile`, `odr_active`, `selected_model`, `odr_run_id`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`, `odr_requirement`, `odr_rounds_completed`, `odr_accepted`

## Guard Lifecycle
1. `guard_approved`
   - `run_id`, `issue_id`, `seat`, `review_payload`
2. `guard_rejected`
   - `run_id`, `issue_id`, `seat`, `review_payload`
3. `guard_requested_changes`
   - `run_id`, `issue_id`, `seat`, `review_payload`
4. `guard_review_payload`
   - `run_id`, `issue_id`, `payload`

## Sandbox Lifecycle
1. `sandbox.runtime_health_observed`
   - `restart_summary`, `health_summary`, `terminal_reason`
2. `sandbox.restart_loop_classified`
   - `restart_summary`, `health_summary`, `terminal_reason`
3. `sandbox.workflow_terminal_outcome`
   - `reason_code`, `required_evidence_ref`, `terminal_at`, `cleanup_due_at`, `state`, `cleanup_state`
4. `sandbox.policy_terminal_outcome`
   - `reason_code`, `required_evidence_ref`, `terminal_at`, `cleanup_due_at`, `state`, `cleanup_state`
5. `sandbox.lifecycle_terminal_outcome`
   - `reason_code`, `required_evidence_ref`, `terminal_at`, `cleanup_due_at`, `state`, `cleanup_state`
6. `sandbox.cleanup_decision_evaluated`
   - `reason_code`, `policy_match`, `dry_run`, `cleanup_strategy`, `cleanup_result`, `compose_path_available`, `authority_reason_codes`, `fallback_resource_names`, `blocked_resource_names`
7. `sandbox.cleanup_execution_result`
   - `reason_code`, `policy_match`, `dry_run`, `cleanup_strategy`, `cleanup_result`, `compose_path_available`, `authority_reason_codes`, `fallback_resource_names`, `blocked_resource_names`, `error`
