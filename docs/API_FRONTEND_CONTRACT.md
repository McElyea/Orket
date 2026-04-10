# Frontend API Contract

Last verified against `orket/interfaces/api.py`: 2026-04-09

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

## Base Health
1. `GET /health`
2. `GET /v1/version`
3. `GET /v1/system/heartbeat`
4. `GET /v1/system/metrics`
5. `GET /v1/system/provider-status`
6. `GET /v1/system/health-view`
7. `WS /ws/events`

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
3. `GET /v1/runs/view`
4. `GET /v1/runs/{session_id}`
5. `GET /v1/runs/{session_id}/view`
6. `GET /v1/runs/{session_id}/metrics`
7. `GET /v1/runs/{session_id}/token-summary`
8. `GET /v1/runs/{session_id}/replay`
9. `GET /v1/runs/{session_id}/backlog`
10. `GET /v1/runs/{session_id}/execution-graph`
11. `GET /v1/sessions/{session_id}`
12. `GET /v1/sessions/{session_id}/status`
13. `GET /v1/sessions/{session_id}/replay`
14. `GET /v1/sessions/{session_id}/snapshot`
15. `POST /v1/sessions/{session_id}/halt`

## Operator Approval Control
1. `GET /v1/approvals`
2. `GET /v1/approvals/{approval_id}`
3. `POST /v1/approvals/{approval_id}/decision`

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
6. The active SupervisorRuntime approval-checkpoint contract uses the approval endpoints above for three shipped bounded slices only: governed kernel `NEEDS_APPROVAL` on the default `session:<session_id>` namespace scope, plus governed turn-tool `write_file` and `create_issue` approval-required continuation on the default `issue:<issue_id>` namespace scope using `request_type=tool_approval`, `reason=approval_required_tool:<tool_name>`, and the existing `control_plane_target_ref`; no broader approval-required tool family or manual resume API is admitted.
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
36. `GET /v1/runs/view` supports optional `limit`.
37. `GET /v1/flows` supports optional `limit` and `offset`.
38. `POST /v1/flows` body requires `definition` with the admitted `FlowDefinitionWriteModel` fields from [docs/specs/FLOW_AUTHORING_SURFACE_V1.md](docs/specs/FLOW_AUTHORING_SURFACE_V1.md).
39. `PUT /v1/flows/{flow_id}` body requires `definition` and supports optional `expected_revision_id`; it fails closed with `404` when the flow does not exist and `409` on revision conflict.
40. `POST /v1/flows/validate` body requires `definition`; it is non-persisting and does not mint a host `flow_id`.
41. `POST /v1/flows/{flow_id}/runs` supports optional `expected_revision_id`; the current admitted run slice is bounded to exactly one `card` node, forbids `branch` and `merge`, requires the assigned card on the host card surface, requires that card to resolve on the canonical run-card surface including the bounded authored-card runtime projection documented by [docs/specs/CARD_AUTHORING_SURFACE_V1.md](docs/specs/CARD_AUTHORING_SURFACE_V1.md) when applicable, and requires that card to resolve to the `issue` runtime target.
42. `POST /v1/flows/{flow_id}/runs` returns authoritative acceptance through `session_id` when it succeeds; later run completion remains governed by the existing runtime policy and epic environment.
43. `POST /v1/system/run-active` body supports: `path`, `build_id`, `type`, `issue_id`; it remains the canonical run/rerun action for the Card Viewer/Runner slice.
44. `GET /v1/system/provider-status` and `GET /v1/system/health-view` support optional `roles`.
45. `PATCH /v1/settings` accepts runtime setting updates defined in `SETTINGS_SCHEMA`.
46. Orket host does not mount Companion-named product routes; clients that need Companion product behavior must go through the external Companion BFF.
47. `extension_id` on `/v1/extensions/{extension_id}/runtime/*` must be a non-empty admitted id segment matching `[A-Za-z0-9._-]{1,128}`.
48. `GET /v1/extensions/{extension_id}/runtime/status` returns capability availability plus `voice_state`, `voice_silence_delay_sec`, and `active_sessions`.
49. `GET /v1/extensions/{extension_id}/runtime/models` supports optional `provider`; current default is `ollama`.
50. `POST /v1/extensions/{extension_id}/runtime/llm/generate` requires: `user_message`; supports optional `system_prompt`, `max_tokens`, `temperature`, `stop_sequences`, `provider`, `model`.
51. `POST /v1/extensions/{extension_id}/runtime/memory/query` requires: `scope` with admitted values `session_memory`, `profile_memory`, or `episodic_memory`; `session_id` is required for non-profile scopes; supports optional `query`, `limit`.
52. `POST /v1/extensions/{extension_id}/runtime/memory/write` requires: `scope`, `key`; `session_id` is required for non-profile scopes; supports optional `metadata`.
53. `POST /v1/extensions/{extension_id}/runtime/memory/clear` requires: `scope` with admitted values `session_memory` or `episodic_memory`, plus `session_id`.
54. `POST /v1/extensions/{extension_id}/runtime/voice/control` requires: `command` with admitted values `start`, `stop`, or `submit`; supports optional `silence_delay_sec`.
55. `POST /v1/extensions/{extension_id}/runtime/voice/transcribe` requires: `audio_b64`; supports optional `mime_type`, `language_hint`.
56. `POST /v1/extensions/{extension_id}/runtime/tts/synthesize` requires: `text`; supports optional `voice_id`, `emotion_hint`, `speed`.
57. `GET /v1/marshaller/runs` supports optional `limit`.
58. `GET /v1/marshaller/runs/{run_id}` supports optional `attempt_index`.
59. `WS /ws/interactions/{session_id}` is a session-scoped interaction event stream and fails closed when stream events v1 is disabled.

## Compatibility Rule
When routes or payload shapes change, update this document in the same PR.
