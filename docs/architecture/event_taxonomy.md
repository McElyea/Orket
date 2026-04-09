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
2. `tool_recovery_partial`
   - `issue_id`, `role`, `session_id`, `turn_index`, `recovered_count`, `skipped_tools`, `result`

## Tool Lifecycle
1. `tool_call_start`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `args`
2. `tool_call_blocked`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `args`, `reason`
3. `tool_approval_required`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `request_id`, `stage_gate_mode`
4. `tool_approval_granted`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `request_id`, `stage_gate_mode`
5. `tool_call_result`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `ok`, `error`
6. `tool_call_exception`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `error`
7. `tool_call_replayed`
   - `issue_id`, `session_id`, `turn_index`, `tool`
8. `determinism_violation`
   - `issue_id`, `session_id`, `turn_index`, `tool`, `error`, `error_code`, `determinism_class`, `capability_profile`, `tool_contract_version`, `side_effect_signal_keys`
9. `tool_timeout`
   - `tool`, `timeout_seconds`, `ok`, `error`
10. `interceptor_error`
   - `hook`, `interceptor`, `error`
11. `sdk_capability_call_start`
   - `extension_id`, `workload_id`, `run_id`, `capability_id`, `capability_family`, `authorization_basis`, `declared`, `admitted`, `side_effect_observed`
12. `sdk_capability_call_blocked`
   - `extension_id`, `workload_id`, `run_id`, `capability_id`, `capability_family`, `authorization_basis`, `declared`, `admitted`, `side_effect_observed`, `denial_class`
13. `sdk_capability_call_result`
   - `extension_id`, `workload_id`, `run_id`, `capability_id`, `capability_family`, `authorization_basis`, `declared`, `admitted`, `side_effect_observed`
14. `sdk_capability_call_exception`
   - `extension_id`, `workload_id`, `run_id`, `capability_id`, `capability_family`, `authorization_basis`, `declared`, `admitted`, `side_effect_observed`, `error_code`, `error`

`determinism_violation` is emitted to the runtime event artifact stream at `agent_output/observability/runtime_events.jsonl` when a tool's observed side effects contradict its declared determinism class.

Legacy `tool_blocked` from direct `Agent.run(...)` remains compatibility telemetry and is not part of the canonical governed turn-tool event family.

## Agent Factory Lifecycle
1. `seat_no_roles_configured`
   - `team`, `seat`
2. `seat_role_config_missing`
   - `team`, `seat`, `role`
3. `model_family_unrecognized`
   - `agent`, `model`, `family`

## Logging Lifecycle
1. `log_write_queue_full`
   - `dropped_log_entries`, `queue_max`, `path`

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
   - `session_id`, `issue_id`, `execution_profile`, `odr_active`, `selected_model`, `odr_run_id`, `audit_mode`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`, `odr_requirement`, `odr_rounds_completed`, `last_valid_round_index`, `last_emitted_round_index`, `odr_accepted`
10. `odr_prebuild_failed`
   - `session_id`, `issue_id`, `execution_profile`, `odr_active`, `selected_model`, `odr_run_id`, `audit_mode`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`, `odr_requirement`, `odr_rounds_completed`, `last_valid_round_index`, `last_emitted_round_index`, `odr_accepted`
11. `turn_retry_scheduled`
   - `issue_id`, `role`, `session_id`, `turn_index`, `retry_count`, `max_retries`, `backoff_seconds`, `error_type`, `error`
12. `turn_retry_exhausted`
   - `issue_id`, `role`, `session_id`, `turn_index`, `retry_count`, `max_retries`, `error_type`, `error`, `result`
13. `lease_acquisition_failed`
   - `card_id`, `worker_id`, `wait_reason`, `result` (`skipped` when no lease was acquired and no state transition occurred)
14. `state_reconciliation_conflict`
   - `card_id`, `sqlite_state`, `gitea_state`, `gitea_version`, `authority_policy`, `result`, `conflict_type`

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
