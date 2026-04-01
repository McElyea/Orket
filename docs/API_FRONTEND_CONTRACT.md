# Frontend API Contract

Last verified against `orket/interfaces/api.py`: 2026-04-01

## Authentication
1. `/v1/*` endpoints require `X-API-Key`.
2. Companion route key-scoping:
   - `/v1/companion/*` and `/api/v1/companion/*` accept `ORKET_COMPANION_API_KEY` when configured.
   - Compatibility mode (default): `ORKET_API_KEY` is still accepted on Companion routes for operator/admin access.
   - Strict mode (`ORKET_COMPANION_KEY_STRICT=true`): Companion routes reject `ORKET_API_KEY` when `ORKET_COMPANION_API_KEY` is configured.
   - Non-Companion `/v1/*` routes do not accept `ORKET_COMPANION_API_KEY`.
   - Auth rejection telemetry is emitted via `api_auth_rejected` with `route_class` (`companion` or `core`) and reason code.
3. Websocket endpoint `GET ws://<host>/ws/events` accepts API key via:
   - `X-API-Key` header, or
   - `api_key` query parameter.
4. Fail-closed default: requests are rejected when `ORKET_API_KEY` is unset.
5. Insecure bypass exists only when `ORKET_ALLOW_INSECURE_NO_API_KEY=true`.

## Base Health
1. `GET /health`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/metrics`
5. `WS /ws/events`

## Kernel Endpoints
1. `POST /v1/kernel/lifecycle`
2. `POST /v1/kernel/compare`
3. `POST /v1/kernel/replay`
4. `POST /v1/kernel/projection-pack`
5. `POST /v1/kernel/admit-proposal`
6. `POST /v1/kernel/commit-proposal`
7. `POST /v1/kernel/end-session`
8. `GET /v1/kernel/ledger-events`
9. `POST /v1/kernel/approvals/rebuild`
10. `GET /v1/kernel/action-lifecycle/replay`
11. `GET /v1/kernel/action-lifecycle/audit`

## Runtime Control and Introspection
1. `POST /v1/system/run-active`
2. `GET /v1/runs`
3. `GET /v1/runs/{session_id}`
4. `GET /v1/runs/{session_id}/metrics`
5. `GET /v1/runs/{session_id}/token-summary`
6. `GET /v1/runs/{session_id}/replay`
7. `GET /v1/runs/{session_id}/backlog`
8. `GET /v1/runs/{session_id}/execution-graph`
9. `GET /v1/sessions/{session_id}`
10. `GET /v1/sessions/{session_id}/status`
11. `GET /v1/sessions/{session_id}/replay`
12. `GET /v1/sessions/{session_id}/snapshot`
13. `POST /v1/sessions/{session_id}/halt`

## Operator Approval Control
1. `GET /v1/approvals`
2. `GET /v1/approvals/{approval_id}`
3. `POST /v1/approvals/{approval_id}/decision`

## Interaction Sessions and Turn Control
1. `POST /v1/interactions/sessions`
2. `POST /v1/interactions/{session_id}/turns`
3. `POST /v1/interactions/{session_id}/finalize`
4. `POST /v1/interactions/{session_id}/cancel`

## Protocol Replay and Parity
1. `GET /v1/protocol/runs/{run_id}/replay`
2. `GET /v1/protocol/replay/compare`
3. `GET /v1/protocol/replay/campaign`
4. `GET /v1/protocol/runs/{run_id}/ledger-parity`
5. `GET /v1/protocol/ledger-parity/campaign`

## Files and System Utilities
1. `GET /v1/system/explorer`
2. `GET /v1/system/read`
3. `POST /v1/system/save`
4. `GET /v1/system/calendar`
5. `GET /v1/system/board`
6. `GET /v1/system/preview-asset`
7. `POST /v1/system/chat-driver`
8. `GET /v1/logs`
9. `POST /v1/system/clear-logs`

## Cards
1. `GET /v1/cards`
2. `GET /v1/cards/{card_id}`
3. `GET /v1/cards/{card_id}/history`
4. `GET /v1/cards/{card_id}/guard-history`
5. `GET /v1/cards/{card_id}/comments`
6. `POST /v1/cards/archive`

## Sandboxes
1. `GET /v1/sandboxes`
2. `POST /v1/sandboxes/{sandbox_id}/stop`
3. `GET /v1/sandboxes/{sandbox_id}/logs`

## Runtime Policy and Settings
1. `GET /v1/system/runtime-policy/options`
2. `GET /v1/system/runtime-policy`
3. `POST /v1/system/runtime-policy`
4. `GET /v1/system/model-assignments`
5. `GET /v1/system/teams`
6. `GET /v1/settings`
7. `PATCH /v1/settings`

## Query/Body Notes
1. `GET /v1/logs` supports: `session_id`, `event`, `role`, `start_time`, `end_time`, `limit`, `offset`.
2. `GET /v1/sessions/{session_id}/replay` supports optional `issue_id`, `turn_index`, `role`; when `issue_id` and `turn_index` are both omitted it returns a replay timeline, and when either is provided both are required.
3. `GET /v1/approvals` supports: `status`, `session_id`, `request_id`, `limit`; Packet 1 admits `status` values `PENDING`, `APPROVED`, and `DENIED` only.
4. `GET /v1/approvals` and `GET /v1/approvals/{approval_id}` fail closed with conflict when the Packet 1 approval row carries an unsupported legacy lifecycle status or when payload-versus-reservation/operator-action projection truth drifts.
5. `POST /v1/approvals/{approval_id}/decision` body requires: `decision` with admitted values `approve` or `deny`; optional `edited_proposal`, `notes` are accepted as bounded operator metadata and do not create alternate execution authority.
6. The completed SupervisorRuntime Packet 1 approval-checkpoint contract uses the approval endpoints above for the governed kernel `NEEDS_APPROVAL` lifecycle on the default `session:<session_id>` namespace scope; turn-tool approval-required requests may appear on these surfaces but do not form an approve-to-continue Packet 1 execution contract.
7. `POST /v1/kernel/projection-pack` requires: `session_id`, `trace_id`; supports optional `request_id`, `canonical_state_digest`, `purpose`, `tool_context_summary`, `policy_context`.
8. `POST /v1/kernel/admit-proposal` requires: `session_id`, `trace_id`, `proposal`.
9. `POST /v1/kernel/commit-proposal` requires: `session_id`, `trace_id`, `proposal_digest`, `admission_decision_digest`; supports optional `approval_id`, `execution_result_digest`, `execution_result_payload`, `execution_result_schema_valid`, `execution_error_reason_code`, `sanitization_digest`, `revalidate_policy_forbidden`, `canonical_state_digest_after`, `block_result_leaks`.
10. `POST /v1/kernel/end-session` requires: `session_id`, `trace_id`; supports optional `request_id`, `reason`, `attestation_scope`, `attestation_payload`.
11. `GET /v1/kernel/ledger-events` requires: `session_id`; supports optional `trace_id`, `event_type`, `limit`.
12. `POST /v1/kernel/approvals/rebuild` requires: `session_id`.
13. `GET /v1/kernel/action-lifecycle/replay` requires: `session_id`, `trace_id`.
14. `GET /v1/kernel/action-lifecycle/audit` requires: `session_id`, `trace_id`.
15. `POST /v1/interactions/sessions` body supports: `session_params`; the host creates the canonical `session_id`.
16. `POST /v1/interactions/{session_id}/turns` body supports: `workload_id`, `input_config`, `department`, `workspace`, `turn_params`.
17. `POST /v1/interactions/{session_id}/turns` keeps Packet 1 context-provider inputs bounded to `session_params`, `input_config`, `turn_params`, `workload_id`, `department`, `workspace`, and host-resolved extension-manifest `required_capabilities` when the extension path is used.
18. `POST /v1/interactions/{session_id}/turns` fails closed when `workspace` escapes the configured workspace root.
19. `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot` are host-owned inspection surfaces keyed by the canonical `session_id`.
20. `POST /v1/sessions/{session_id}/halt` and `POST /v1/interactions/{session_id}/cancel` are cleanup-adjacent operator commands only; they do not imply session deletion or workspace cleanup.
21. `POST /v1/interactions/{session_id}/finalize` requires: `turn_id`.
22. `POST /v1/interactions/{session_id}/cancel` body supports optional `turn_id`.
23. `GET /v1/protocol/runs/{run_id}/replay` is an inspection-only reconstruction surface for one protocol run.
24. `GET /v1/protocol/replay/compare` requires: `run_a`, `run_b`.
25. `GET /v1/protocol/replay/campaign` supports repeated `run_id`; optional `baseline_run`, `runs_root`.
26. `GET /v1/protocol/runs/{run_id}/ledger-parity` supports optional `sqlite_db_path`.
27. `GET /v1/protocol/ledger-parity/campaign` supports repeated `session_id`; optional `sqlite_db_path`, `discover_limit`.
28. Caller-provided `runs_root` and `sqlite_db_path` on the protocol replay or parity surfaces fail closed when they escape the workspace root.
29. `POST /v1/cards/archive` requires at least one selector: `card_ids`, `build_id`, or `related_tokens`.
30. `POST /v1/system/run-active` body supports: `path`, `build_id`, `type`, `issue_id`.
31. `PATCH /v1/settings` accepts runtime setting updates defined in `SETTINGS_SCHEMA`.

## Compatibility Rule
When routes or payload shapes change, update this document in the same PR.
