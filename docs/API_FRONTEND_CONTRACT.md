# Frontend API Contract

Last verified against `orket/interfaces/api.py`: 2026-04-25

## Authentication
1. `/v1/*` endpoints require `X-API-Key`.
2. Generic extension runtime routes under `/v1/extensions/{extension_id}/runtime/*` use the same `ORKET_API_KEY` posture as other core `/v1/*` routes.
3. Orket host no longer mounts Companion-specific product routes under `/v1/companion/*` or `/api/v1/companion/*`.
4. Auth rejection telemetry is emitted via `api_auth_rejected` with `route_class=core`.
5. Websocket endpoints `GET ws://<host>/ws/events` and `GET ws://<host>/ws/interactions/{session_id}` accept API key via:
   - `X-API-Key` header, or
   - `api_key` query parameter.
6. Fail-closed default: requests are rejected when `ORKET_API_KEY` is unset.
7. Insecure bypass exists only when `ORKET_ALLOW_INSECURE_NO_API_KEY=true`.
8. Every HTTP response under `/v1/*` includes `X-Orket-Version`.

## Browser CORS
1. CORS defaults to `allow_origins=[]`; browser clients are denied unless the host operator configures an explicit allowlist.
2. Set `ORKET_ALLOWED_ORIGINS` to comma-separated trusted origins, for example `http://localhost:5173,http://127.0.0.1:5173`.
3. CORS credentials are disabled by default.

## Base Health
1. `GET /health`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/metrics`
5. `GET /v1/system/provider-status`
6. `GET /v1/system/health-view`
7. `WS /ws/events`

`GET /health` is intentionally unauthenticated and minimal. Its default response body is only:

```json
{ "status": "ok" }
```

Use authenticated `/v1/*` system surfaces for version, metrics, provider, and detailed health data.

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
1. `POST /v1/runs`
2. `POST /v1/system/run-active`
3. `GET /v1/runs`
4. `GET /v1/runs/view`
5. `GET /v1/runs/{session_id}`
6. `GET /v1/runs/{session_id}/view`
7. `GET /v1/runs/{session_id}/metrics`
8. `GET /v1/runs/{session_id}/token-summary`
9. `GET /v1/runs/{session_id}/events`
10. `GET /v1/runs/{session_id}/events/stream`
11. `GET /v1/runs/{session_id}/summary`
12. `GET /v1/runs/{session_id}/ledger`
13. `GET /v1/runs/{session_id}/ledger/verify`
14. `GET /v1/runs/{session_id}/replay`
15. `GET /v1/runs/{session_id}/backlog`
16. `GET /v1/runs/{session_id}/execution-graph`
17. `GET /v1/sessions/{session_id}`
18. `GET /v1/sessions/{session_id}/status`
19. `GET /v1/sessions/{session_id}/replay`
20. `GET /v1/sessions/{session_id}/snapshot`
21. `POST /v1/sessions/{session_id}/halt`

## Operator Approval Control
1. `GET /v1/approvals`
2. `GET /v1/approvals/{approval_id}`
3. `POST /v1/approvals/{approval_id}/decision`
4. `POST /v1/approvals/{approval_id}/approve`
5. `POST /v1/approvals/{approval_id}/deny`

## Interaction Sessions and Turn Control
1. `POST /v1/interactions/sessions`
2. `POST /v1/interactions/{session_id}/turns`
3. `POST /v1/interactions/{session_id}/finalize`
4. `POST /v1/interactions/{session_id}/cancel`
5. `WS /ws/interactions/{session_id}`

## Generic Extension Runtime Host API
1. `GET /v1/extensions/{extension_id}/runtime/status`
2. `GET /v1/extensions/{extension_id}/runtime/models`
3. `POST /v1/extensions/{extension_id}/runtime/llm/generate`
4. `POST /v1/extensions/{extension_id}/runtime/memory/query`
5. `POST /v1/extensions/{extension_id}/runtime/memory/write`
6. `POST /v1/extensions/{extension_id}/runtime/memory/clear`
7. `GET /v1/extensions/{extension_id}/runtime/voice/state`
8. `POST /v1/extensions/{extension_id}/runtime/voice/control`
9. `POST /v1/extensions/{extension_id}/runtime/voice/transcribe`
10. `GET /v1/extensions/{extension_id}/runtime/tts/voices`
11. `POST /v1/extensions/{extension_id}/runtime/tts/synthesize`

## Companion BFF Ownership Note
1. Companion product routes now live only in the external Companion gateway/BFF.
2. The outward Companion BFF route family remains `/api/*` in the external Companion repo.
3. That BFF translates product requests into the generic host runtime routes above.
4. Those `/api/*` routes are not mounted in Orket core.

## Marshaller Inspection
1. `GET /v1/marshaller/runs`
2. `GET /v1/marshaller/runs/{run_id}`

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
2. `GET /v1/cards/view`
3. `GET /v1/cards/{card_id}`
4. `GET /v1/cards/{card_id}/view`
5. `GET /v1/cards/{card_id}/history`
6. `GET /v1/cards/{card_id}/guard-history`
7. `GET /v1/cards/{card_id}/comments`
8. `POST /v1/cards`
9. `PUT /v1/cards/{card_id}`
10. `POST /v1/cards/validate`
11. `POST /v1/cards/archive`

## Flows
1. `GET /v1/flows`
2. `GET /v1/flows/{flow_id}`
3. `POST /v1/flows`
4. `PUT /v1/flows/{flow_id}`
5. `POST /v1/flows/validate`
6. `POST /v1/flows/{flow_id}/runs`

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
6. The active SupervisorRuntime approval-checkpoint contract uses the approval endpoints above for four shipped bounded slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file`, `create_directory`, and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope using `request_type=tool_approval`, `reason=approval_required_tool:<tool_name>`, and the existing `control_plane_target_ref`; no broader approval-required tool family or manual resume API is admitted.
7. `POST /v1/kernel/projection-pack` requires: `session_id`, `trace_id`; supports optional `request_id`, `canonical_state_digest`, `purpose`, `tool_context_summary`, `policy_context`, and `outbound_policy` with redaction settings applied before projection digesting.
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
19. `GET /v1/sessions/{session_id}`, `GET /v1/sessions/{session_id}/status`, `GET /v1/sessions/{session_id}/replay`, and `GET /v1/sessions/{session_id}/snapshot` are host-owned inspection surfaces keyed by the canonical `session_id`; on the admitted interaction-session path, `/snapshot` returns inspection-only session-context lineage including `context_version`, ordered `provider_lineage`, and the latest bounded Packet 1 context envelope, and `/replay` without `issue_id` plus `turn_index` returns the interaction-turn timeline view.
20. Targeted replay with both `issue_id` and `turn_index` remains run-session-only and fails closed on interaction sessions.
21. `POST /v1/sessions/{session_id}/halt` and `POST /v1/interactions/{session_id}/cancel` are cleanup-adjacent operator commands only; they do not imply session deletion or workspace cleanup.
22. `POST /v1/interactions/{session_id}/finalize` requires: `turn_id`.
23. `POST /v1/interactions/{session_id}/cancel` body supports optional `turn_id`.
24. `GET /v1/protocol/runs/{run_id}/replay` is an inspection-only reconstruction surface for one protocol run.
25. `GET /v1/protocol/replay/compare` requires: `run_a`, `run_b`.
26. `GET /v1/protocol/replay/campaign` supports repeated `run_id`; optional `baseline_run`, `runs_root`.
27. `GET /v1/protocol/runs/{run_id}/ledger-parity` supports optional `sqlite_db_path`.
28. `GET /v1/protocol/ledger-parity/campaign` supports repeated `session_id`; optional `sqlite_db_path`, `discover_limit`.
29. Caller-provided `runs_root` and `sqlite_db_path` on the protocol replay or parity surfaces fail closed when they escape the workspace root.
30. `POST /v1/cards` body requires `draft` with the admitted `CardDraftWriteModel` fields from [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md).
31. `PUT /v1/cards/{card_id}` body requires `draft` and supports optional `expected_revision_id`; it fails closed with `404` when the card does not exist and `409` on revision conflict. For issue-target authored cards, successful `POST` and `PUT` also upsert the bounded runtime projection at `config/epics/orket_ui_authored_cards.json` so the current admitted flow-run slice can resolve those cards on the canonical run-card surface.
32. `POST /v1/cards/validate` body requires `draft`; it is non-persisting and does not mint a host `card_id`.
33. `POST /v1/cards/archive` requires at least one selector: `card_ids`, `build_id`, or `related_tokens`.
34. `GET /v1/cards/view` supports optional `build_id`, `session_id`, `status`, `filter`, `limit`, `offset`; `filter` admits `open`, `running`, `blocked`, `review`, `terminal_failure`, and `completed`.
35. `GET /v1/cards/view`, `GET /v1/cards/{card_id}/view`, `GET /v1/runs/view`, and `GET /v1/runs/{session_id}/view` are the canonical operator-facing Card Viewer/Runner read surfaces and return the stable read models defined in `docs/specs/CARD_VIEWER_RUNNER_SURFACE_V1.md`.
36. `POST /v1/runs` accepts optional `run_id`, optional `namespace`, required `task.description`, required `task.instruction`, optional `task.acceptance_contract`, and optional `policy_overrides` with `approval_required_tools`, `max_turns`, and `approval_timeout_seconds`. It is idempotent on `run_id`, returns the persisted outward run status payload, and creates the initial `run_submitted` ledger event. When `task.acceptance_contract.governed_tool_call` is present, the Phase 2 outward execution slice treats it as one explicit governed tool gate. When `task.acceptance_contract.governed_tool_sequence` is present, the slice treats it as an ordered governed-turn sequence and asks the configured model for one tool call per turn. Absence of both fields keeps the run queued.
37. `GET /v1/runs` supports outward run filtering with optional `status`, `limit`, and `offset`; when no outward run records exist and no outward filter or pagination is requested, it preserves the legacy session-list compatibility behavior.
38. `GET /v1/runs/{session_id}` returns an outward run status payload when `{session_id}` is a known outward `run_id`; otherwise it preserves the legacy session/run-ledger detail behavior.
39. `GET /v1/runs/view` supports optional `limit`.
40. `GET /v1/flows` supports optional `limit` and `offset`.
41. `POST /v1/flows` body requires `definition` with the admitted `FlowDefinitionWriteModel` fields from [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md).
42. `PUT /v1/flows/{flow_id}` body requires `definition` and supports optional `expected_revision_id`; it fails closed with `404` when the flow does not exist and `409` on revision conflict.
43. `POST /v1/flows/validate` body requires `definition`; it is non-persisting and does not mint a host `flow_id`.
44. `POST /v1/flows/{flow_id}/runs` supports optional `expected_revision_id`; the current admitted run slice is bounded to exactly one `card` node, forbids `branch` and `merge`, requires the assigned card on the host card surface, requires that card to resolve on the canonical run-card surface including the bounded authored-card runtime projection documented by [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md) when applicable, and requires that card to resolve to the `issue` runtime target.
45. `POST /v1/flows/{flow_id}/runs` returns authoritative acceptance through `session_id` when it succeeds; later run completion remains governed by the existing runtime policy and epic environment.
46. `POST /v1/system/run-active` body supports: `path`, `build_id`, `type`, `issue_id`; it remains the canonical run/rerun action for the Card Viewer/Runner slice.
47. `GET /v1/system/provider-status` and `GET /v1/system/health-view` support optional `roles`.
48. `PATCH /v1/settings` accepts runtime setting updates defined in `SETTINGS_SCHEMA`.
49. Orket host does not mount Companion-named product routes; clients that need Companion product behavior must go through the external Companion BFF.
50. `extension_id` on `/v1/extensions/{extension_id}/runtime/*` must be a non-empty admitted id segment matching `[A-Za-z0-9._-]{1,128}`.
51. `GET /v1/extensions/{extension_id}/runtime/status` returns capability availability plus `voice_state`, `voice_silence_delay_sec`, and `active_sessions`.
52. `GET /v1/extensions/{extension_id}/runtime/models` supports optional `provider`; current default is `ollama`.
53. `POST /v1/extensions/{extension_id}/runtime/llm/generate` requires: `user_message`; supports optional `system_prompt`, `max_tokens`, `temperature`, `stop_sequences`, `provider`, `model`.
54. `POST /v1/extensions/{extension_id}/runtime/memory/query` requires: `scope` with admitted values `session_memory`, `profile_memory`, or `episodic_memory`; `session_id` is required for non-profile scopes; supports optional `query`, `limit`.
55. `POST /v1/extensions/{extension_id}/runtime/memory/write` requires: `scope`, `key`; `session_id` is required for non-profile scopes; supports optional `metadata`.
56. `POST /v1/extensions/{extension_id}/runtime/memory/clear` requires: `scope` with admitted values `session_memory` or `episodic_memory`, plus `session_id`.
57. `POST /v1/extensions/{extension_id}/runtime/voice/control` requires: `command` with admitted values `start`, `stop`, or `submit`; supports optional `silence_delay_sec`.
58. `POST /v1/extensions/{extension_id}/runtime/voice/transcribe` requires: `audio_b64`; supports optional `mime_type`, `language_hint`.
59. `POST /v1/extensions/{extension_id}/runtime/tts/synthesize` requires: `text`; supports optional `voice_id`, `emotion_hint`, `speed`.
60. `GET /v1/marshaller/runs` supports optional `limit`.
61. `GET /v1/marshaller/runs/{run_id}` supports optional `attempt_index`.
62. `WS /ws/interactions/{session_id}` is a session-scoped interaction event stream and fails closed when stream events v1 is disabled.
63. Outward-facing approval proposals use lowercase statuses `pending`, `approved`, `denied`, and `expired`; `GET /v1/approvals` and `GET /v1/approvals/{approval_id}` return outward proposals when matching outward approval rows exist, otherwise they preserve the legacy Packet 1 approval behavior.
64. `POST /v1/approvals/{approval_id}/approve` accepts optional `note`, resolves a pending outward proposal idempotently, and continues the explicit outward governed connector execution slice when the approved proposal belongs to a submitted governed tool call or sequence; `POST /v1/approvals/{approval_id}/deny` requires `reason`, accepts optional `note`, records `proposal_denied`, and completes the outward execution slice without invoking the connector effect.
65. `POST /v1/approvals/{approval_id}/decision` remains the Packet 1 compatibility decision endpoint and can resolve an outward proposal when the id matches a stored outward proposal; outward approve-and-pause semantics are not exposed.
66. `GET /v1/runs/{session_id}/events` returns ordered outward `run_events` for a known outward `run_id`; it supports optional `from_turn`, `to_turn`, `types` as comma-separated event types, `agent_id`, and `limit`.
67. `GET /v1/runs/{session_id}/summary` returns a derived outward run summary from the persisted outward run record and `run_events`; it is read-only and does not derive authority from presentation text.
68. `GET /v1/runs/{session_id}/events/stream` returns `text/event-stream` for outward run events using process-local polling over persisted `run_events`; it closes when the outward run is terminal, and after restart clients should use the events endpoint for persisted history until durable pub/sub is implemented.
69. `GET /v1/runs/{session_id}/ledger` returns `ledger_export.v1` JSON for an outward run. Optional `types` accepts ledger event groups `proposals`, `decisions`, `commitments`, `tools`, `audit`, or `all`; filtered exports are `partial_view` payloads with canonical hash-chain anchors. Optional `include_pii=true` records a `ledger_export_requested` audit event before response serialization.
70. `GET /v1/runs/{session_id}/ledger/verify` verifies stored outward `run_events` in the live instance and returns the `ledger_export.v1` verification vocabulary `valid`, `partial_valid`, or `invalid`.
71. Outward governed connector execution uses the built-in connector registry for `read_file`, `write_file`, `create_directory`, `delete_file`, `run_command`, `http_get`, and `http_post`. Connector args are validated before proposal creation, approved invocations emit `tool_invoked` payloads with `connector_name`, `args_hash`, `result_summary`, `duration_ms`, and `outcome`, and HTTP connectors require `ORKET_CONNECTOR_HTTP_ALLOWLIST`.
72. Operator-visible outward payloads pass through `orket/kernel/v1/outbound_policy_gate.py` before serialization. The gate supports configured PII field paths, forbidden regex patterns, and allowed output fields by event/surface type through environment variables or `ORKET_OUTBOUND_POLICY_CONFIG_PATH`. If default ledger export redaction would alter stored event payload bytes, the API returns a `partial_view` ledger export with omitted-span anchors rather than a false full canonical ledger.

## Compatibility Rule
When routes or payload shapes change, update this document in the same PR.
