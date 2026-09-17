# Event Taxonomy

This document defines canonical runtime events and minimum fields.

## Common Fields
- `timestamp` (ISO8601)
- `role` (actor)
- `event` (event name)
- `data` (object payload)

New normalized `data.runtime_event` envelopes use `schema_version: v2` and
nullable, fractional `duration_ms`; absent or invalid values are null. Existing
v1 history stays unchanged. Connector provenance is defined in
`docs/specs/CONNECTOR_INVOCATION_TIMING.md` and is retained when supplied.

## Model/Prompt Lifecycle

New token payload projections retain `timing_schema_version` and
`timing_posture: reported|partial|unavailable|legacy_unverified` alongside nullable
prompt/predicted durations. Field-availability status alone does not certify
timing evidence. Provider source/scope, legacy reads and complete benchmark
coverage follow `docs/specs/MODEL_PROVIDER_TIMING.md`.

1. `turn_start`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `prompt_hash`, `selected_model`, `execution_profile`, `builder_seat_choice`, `reviewer_seat_choice`, `seat_coercion`, `artifact_contract`, `odr_active`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`
2. `turn_corrective_reprompt`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `reason`, `contract_reasons`
3. `turn_complete`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `duration_ms`, `tool_calls`, `execution_profile`, `builder_seat_choice`, `reviewer_seat_choice`, `seat_coercion`, `artifact_contract`, `odr_active`, `odr_valid`, `odr_pending_decisions`, `odr_stop_reason`, `odr_artifact_path`
4. `turn_non_progress`
   - `issue_id`, `session_id`, `turn_index`, `turn_trace_id`, `reason`

## Operator Driver

Failure and structural publication events:

- `policy_violation_report_saved`: `session_id`, `card_id`, `path`; emitted by the
  application publisher after the report file is written and closed.
- `reconciler_start`: `root_path`; records an attempt, not completion.
- `reconciler_orphan_epic_adopted`: `epic_id`, `department`, `target_rock`; follows
  verified target persistence.
- `reconciler_orphan_issue_adopted`: `issue_id`, `department`, `target_epic`; follows
  verified target persistence.

Invalid structural snapshots emit no adoption event. The application raises a
contextual reconciliation error; existing startup callers record failure and keep
their explicit degraded-startup disposition. Earlier adoption events are not
proof of persisted effects; historical logs are not rewritten.

1. `driver_process_failed`
   - `error`
   - Internal processing errors include `traceback`.
   - Model acceptance-definition refusal includes `action` and
     `failure_kind=acceptance_admission`; `error` is
     `E_CARD_ACCEPTANCE_MODEL_DEFINITION_FORBIDDEN`. This branch occurs before
     structural asset writes and logs to the driver's configured operator workspace.
     It does not emit a successful structural mutation event.

## Dual-ledger Lifecycle

Dual-ledger observations:

- `run_ledger_dual_write_error`: `phase`, `session_id`, `backend`, `error_type`,
  `error`; records an operational backend failure with retained pending intent.
- `run_ledger_dual_write_parity`: `phase`, `session_id`, `parity_ok`,
  `difference_count`, `differences`, `sqlite_digest`, `protocol_digest`,
  `protocol_error`, `parity_error`, `parity_check_error`; `parity_skip_reason` is
  present when a protocol write failed. Parity is a comparison of observed rows,
  not an atomic cross-backend commit guarantee.
- `telemetry_sink_error`: `component=run_ledger_dual_write`, `error_type`, `error`;
  records a failed sink after its owned invocation settles.

These observations follow durable effect checks or explicit failed attempts.
Application logging supplies the common fields when no custom sink is configured.

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

## Outward Pipeline Ledger Lifecycle

The BT-5 shared-authority candidate adds `result`, `final_truth_record_id` and
`final_truth_digest` to new terminal events. The digest binds the shared final
truth payload; `completed` protocol status alone is not a success result.
Explicit offline history adoption appends `outward_authority_adopted`, carrying
the actor, reviewed-run digest, historical ledger anchor, current-input basis,
configuration/policy digests and stopped-owner attestation. For terminal history,
`outward_final_truth_adopted` references that adoption and carries the historical
completion time, outcome, protocol status and the shared final-truth fields.
These are adoption events, not reconstructed historical execution events.
Old event cells and their commitments remain unchanged. Contract and acceptance
limits: `docs/specs/OUTWARD_RUN_AUTHORITY.md`.

Outward pending and decision events commit with their proposal and run projection
under `docs/specs/OUTWARD_APPROVAL_EFFECT_LIFECYCLE_V1.md`. Their existing field
shapes and v1 ordering remain unchanged. A decision event proves the stored
decision, not connector execution or completion.

Outward effect publication now commits `tool_invoked`, applicable turn/terminal
events, run progression and the effect publication marker in one transaction from
a retained connector receipt. Claim/intent/receipt/publication records use the
existing control-plane `EffectJournalEntryRecord` schema and chain, not additional
`run_events` types. Existing v1 ordering and hash recipes remain unchanged;
v2 native retained commitments now follow `docs/specs/OUTWARD_LEDGER_STORAGE_V2.md`;
copied legacy migration and full integrity acceptance remain BT-2 obligations. Explicit pre-intent owner
replacement adds no `run_events` type: its claim entry, `RecoveryDecisionRecord`,
`OperatorActionRecord` and current fence commit in the same transaction. Initial
journal references remain retained; replacement-owner entries include the new
fencing generation.

BT-2 adds no `run_events` event type. Event payloads and canonical v1 hash inputs
remain unchanged. Native append sequence, v2 chain and retained head/count are
storage commitments in the same event/publication transaction. V1 export chains
are read-only projections. `ledger_export_requested` retains its existing audit
payload; its event ID now uses serialized append sequence and `operator_ref`
records the authenticated actor. A v2 retained anchor is separately named export
metadata, not a replacement event taxonomy or a signature.

Model admission adds no `run_events` type. Initial start and next-turn advancement
commit ready admission with their existing events. Model-result publication
commits `proposal_made`, pending approval and run projection with the retained
admission publication marker. The extraction ref/digest identifies the original
immutable observation; its pending-extraction label is not rewritten into current
approval status. Policy rejection and model failure use the same transaction.
Explicit model recovery adds no `run_events` type: retained attempt rows plus
shared recovery/operator records identify the old unresolved computation and new
ready attempt. The published proposal references only its admitted attempt's
artifacts under `model_attempts/<scope-digest>/`; latest aliases are not emitted
for new attempts. Migrated legacy references remain unchanged. Fencing prevents
an old producer from publishing, but makes no provider-cost or cancellation claim.

1. `proposal_made`
   - `run_id`, `namespace`, `tool`, `args_preview`, `context_summary`, `model_invocation_ref`, `model_invocation_sha256`, `model_prompt_redacted_sha256`, `model_response_content_sha256`, `model_response_redacted_sha256`, `proposal_extraction_ref`, `proposal_extraction_sha256`, `provider_name`, `model_name`, `tool_name`, `tool_args_hash`
2. `proposal_pending_approval`
   - `proposal_id`, `run_id`, `namespace`, `tool`, `args_preview`, `context_summary`, `risk_level`, `submitted_at`, `expires_at`, `status`
3. `proposal_approved`
   - `proposal_id`, `run_id`, `namespace`, `tool`, `decision`, `operator_ref`, `decided_at`, `status`
4. `proposal_denied`
   - `proposal_id`, `run_id`, `namespace`, `tool`, `decision`, `operator_ref`, `reason`, `decided_at`, `status`
5. `proposal_policy_rejected`
   - `run_id`, `tool`, `args_preview`, `policy_result`, `reason`, `tool_args_hash`
6. `tool_invoked`
   - `connector_name`, `args_hash`, `result_summary`, `duration_ms`, `timing`, `outcome`
7. `commitment_recorded`
   - `run_id`, `tool`, `outcome`
8. `trust_handoff_verified`
   - `bundle_id`, `source_run_id`, `source_agent_id`, `committed_output_digest`, `source_policy_digest`, `handoff_policy_compatibility_scope_id`, `envelope_digest`, `package_path`
9. `trust_handoff_rejected`
   - `rejection_reason`, `rejection_class`, `bundle_id`, `source_run_id`, `package_path`, `result_class`, `evidence_sufficiency`

## Agent Factory Lifecycle
1. `seat_no_roles_configured`
   - `team`, `seat`
2. `seat_role_config_missing`
   - `team`, `seat`, `role`
3. `model_family_unrecognized`
   - `agent`, `model`, `family`

## Logging Lifecycle
`outward_connector_interrupted` is supporting workspace telemetry, outside the
outward ledger event family. Fields: `connector_name`, `args_hash`, `observation`
(`cancelled` or `unresolved`), `duration_ms`, `timing`, and optional native command
`process_lifetime` (`owned_command.v1`). It makes no effect
completion claim and does not release unresolved dispatch intent.

`outward_command_cancelled` records the shared native supervisor's
`owned_command.v1` lifetime before propagating cancellation. Verification callers
retain `verification_process_cancelled`. Both are supporting observations of
cleanup, with nullable process identities and explicit uncertainty. They are
not effect receipts or durable recovery journals.

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
15. `orchestrator_epic_stopped`
   - `run_id`, `epic`
   - The no-candidate loop reached its workflow stop rule. Empty, canceled,
     archived or otherwise terminal work can stop; this event does not claim
     declared acceptance or successful completion.
16. `orchestrator_epic_complete`
   - `run_id`, `epic`
   - Emitted by application-owned epic publication after a sufficient build acceptance snapshot,
     the existing source-attribution gates, and successful control-plane and run
     ledger finalization. The referenced run retains `card_completion_outcome.v1`.
     Session completion, snapshot capture and success-ledger publication must also
     return successfully before this event is emitted.
     Retained publication recovery also emits this event after confirmed effects.
     Since the BT-3 contract delta dated 2026-09-12, loop policy does not emit this
     event. Historical occurrences do not acquire acceptance retroactively.
17. `orchestrator_stalled`
   - `run_id`, `epic`, `iteration`, `reason`, `backlog`, `dependency_rejections`
   - `dependency_rejections` maps dependent card IDs to unresolved prerequisite
     IDs and their retained-acceptance or build-scope rejection reasons. Lifecycle
     alone does not establish that a prerequisite resolved.
18. `session_end`
   - `run_id`, `status`; optional `failure_reason`, `failure_class`
   - Emitted after session status persistence. Successful epic finalization reaches
     this point only after control-plane and run-ledger finalization. This event
     alone does not establish atomic publication across every runtime store.
19. `success_recorded`
   - `run_id`, `type` (`EPIC_COMPLETED` for the epic path)
   - Emitted after the success-ledger write. The epic path first requires accepted
     completion, finalized control-plane/run-ledger records and snapshot capture.

Epic publication events may repeat if a process dies after emission but before
the publication journal advances. Matching completed reentry verifies retained
effects without emitting them again. This is not exactly-once event delivery.

Preparation recovery adds no completion event type. Existing
`protocol_receipt_materialization_failed`, `run_summary_artifact_write_failed`
and `run_artifact_export_failed` observations now accompany propagated callback
failures. They do not authorize successful publication. Explicit degraded summary
generation remains separate from artifact-write success. `run_artifacts_exported`
records a remotely confirmed Git commit, including confirmation during lost-result
recovery; an export-started journal marker alone is not that result. Unconfirmed
enabled export refuses another push or completion claim. Pending local preparation may repeat its observations after
process interruption; the retained journal remains progress authority.

Retained workload outcomes add no completion event type. A recorded normal return
or failure precedes acceptance inspection and cannot independently authorize
`orchestrator_epic_complete`. Recovery preserves that original termination
observation while applying current acceptance gates. Missing termination evidence
raises `E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN` before another dispatch; surviving card
receipts do not fill in an unobserved return or failure.

## Verification Process Lifecycle

1. `verification_process_cancelled`
   - `schema_version` (`owned_command.v1`), `reason`, `cleanup_confirmed`,
     `capture_complete`, `backend`, `transport_pid`, nullable `supervisor_pid`, nullable `command_pid`,
     `diagnostics`.
   - Native `RuntimeVerifier` and fixture/Docker-client cancellation emit observed process lifetime
     after bounded cleanup, before propagating caller cancellation. False cleanup
     confirmation remains uncertainty; event delivery is not a durable recovery
     journal or proof that an epic may release admission.
   - Contract: `docs/specs/VERIFICATION_PROCESS_LIFETIME_CONTRACT.md`.
2. `fixture_verification_cancelled`, `fixture_verification_uncertain`
   - Native fixtures carry the `owned_command.v1` fields above. Docker fixtures
     carry `schema_version=owned_container.v1`, `name`, `owner_id`, nullable
     `container_id`, nullable `exit_code`, `reason`, `cleanup_confirmed`,
     `capture_complete`, `commands`, and `diagnostics`.
   - Each container command has an operation, nullable CLI return code and the
     native lifetime fields. Container cleanup requires daemon absence observation;
     native CLI cleanup alone is insufficient. Cancellation propagates after the
     cleanup observation. Uncertainty refuses result publication; neither event
     authorizes epic completion, recovery or release of retained admission.
3. `piper_process_cancelled`
   - The shared `owned_command.v1` fields above describe the host Piper native
     command after its supervisor's cleanup wait. Speech text and PCM bytes are
     absent from this event. Cleanup uncertainty remains explicit.
   - This is a diagnostic observation, not a successful speech result or a durable
     workload recovery receipt. Contract: `docs/specs/PIPER_RUNTIME_CONTRACT.md`.

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

## Collection and webhook runtime outcomes
Bug-fix manager events follow the accepted in-memory value and, when configured,
verified store read-back. Their observation timestamps remain logger-owned;
phase timestamps come from the explicit application input clock. These events
are not a transaction or restart journal spanning the database and event files.

| Event | Payload |
| --- | --- |
| `bug_fix_phase_started` | `rock_id`, `ends_at` |
| `bug_fix_phase_extended` | `rock_id`, `new_end`, `reason` |
| `bug_fix_phase_completed` | `rock_id`, `phase2_rock` |

1. `epic_collection_phase_transition`
   - `collection`, `phase` (`bug_fix`). Emitted after every declared member has a
     verified successful outcome and the phase owner has returned from start.
     This is an observation of that owner, not a new durable collection journal.
2. `webhook_run_card_error`
   - `issue_id`, with `error` for an execution exception or `outcome` for a typed
     non-success observation (`runtime_execution_result.v1` or
     `runtime_collection_result.v1`). A successfully scheduled review is not
     evidence that its runtime work completed successfully.

## Governed native invocation lifetime

`child_confirmed_stopped` requires observed teardown of the admitted invocation.
A duplicate refusal reports false for the existing owner; pending native launch
cannot produce a true operator stop acknowledgement merely because its handle is
not captured yet. Cleanup failures propagate and retain the owner for inspection.
Foreign event-loop control refuses with
`E_AGENT_INVOCATION_OWNER:event_loop_mismatch` before changing ownership.
Cancellation payloads are captured before awaiting; child frames, SDK schemas and
request/lease deadline meanings are unchanged. Contract and limits:
`docs/architecture/CONTRACT_DELTA_AGENT_INVOCATION_LIFETIME_D_2026-09-17.md`.

## Protocol run graph publication

A protocol graph projects observed ledger events. Finalization appends its terminal
event before publishing the derived graph; a refused append cannot publish a future
terminal projection. A graph-write failure is reported even when the terminal event
is already durable. Matching finalization retry repairs and verifies the projection
without duplicating that event. `E_FILE_WRITE_UNVERIFIED` names a read-back content
mismatch; its vocabulary authority is the core protocol error catalog. Graphs remain
projections and do not replace terminal ledger authority. The schema/version and
node/edge meanings are unchanged. Contract:
`docs/architecture/CONTRACT_DELTA_PROTOCOL_GRAPH_CD_2026-09-17.md`.

## Provider preparation observations

Provider target payload fields remain unchanged. `auto_load_attempted` records an
actual load command; disabled or unnecessary loading leaves it false. A load
acknowledgement without the candidate in post-load inventory returns
`status: BLOCKED`, `resolution_mode: model_load_unverified` and
`auto_load_performed: false`. Captured settings and immutable target metadata
retain their invocation/client scope; later environment edits are not evidence
that an existing target was re-admitted. Authority and limits:
`docs/architecture/CONTRACT_DELTA_PROVIDER_INPUTS_CD_2026-09-17.md`.
