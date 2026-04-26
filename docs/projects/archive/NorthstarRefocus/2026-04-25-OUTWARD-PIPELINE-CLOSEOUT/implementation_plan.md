# Orket — Implementation Plan: Outward-Facing Pipeline
*Version 1.1 · April 25, 2026*

---

## Purpose

This plan implements the outward-facing Orket pipeline defined in `pipeline_requirements.md`.

The goal is one complete operator-visible loop:

```text
submit work
→ run reaches approval-required action
→ operator approves or denies
→ run records events
→ ledger exports
→ ledger verifies offline
```

This plan does not implement Orket's internal governance process, a graphical UI, benchmark tooling, prompt reforging, marketplace features, or legacy artifact migration.

Canonical documents for this lane are `north_star.md`, `pipeline_requirements.md`, and `implementation_plan.md`. Draft filenames with `_revised` are not part of the accepted authority set.

---

## Execution Rules

1. Work only on requirements in the current phase.
2. File out-of-scope defects instead of fixing them immediately.
3. Do not expand a done condition without updating the requirements first.
4. Every phase must end with a demo or automated test proving the phase outcome.
5. Do not create a separate governance lane for this implementation plan.
6. Prefer the smallest implementation that proves the outward-facing pipeline honestly.

---

## Current State Inventory

This inventory is a planning snapshot, not implementation authority. Inventory refresh: 2026-04-25 against commit `242273f` with an already-dirty worktree. Phase 0 implementation rechecked the foundation rows below before code changes; later phases must refresh their rows before they drive implementation work.

| Component | Status | Plan Use |
|---|---:|---|
| REST API / FastAPI | Exists | Extend `/v1/runs`, approvals, events, ledger |
| Control plane DB | Exists; Phase 0 WAL foundation and outward `run_events` store added | Use as outward pipeline event persistence foundation |
| Run/session model | Exists | Reuse where possible |
| `run_summary.json` | Exists | Use as reference input only where compatible; do not make it the ledger authority |
| Approval checkpoint for `write_file` | Exists | Generalize to v1 governed tool family |
| Observability/lifecycle files | Exist | Do not migrate in Phase 0 unless directly required for outward pipeline |
| Extension SDK | Exists | Harden built-in connector shape first |
| CLI | Exists as Phase 1 API-client skeleton | Extend only through explicit later-phase CLI commands |
| Ledger export | Missing | Add export and offline verify |
| SSE stream | Missing | Add live event stream |
| Outbound policy gate | Exists as Phase 0 no-op serialization boundary | Harden behavior in Phase 6; require new operator-visible surfaces to call it |
| `/health` endpoint | Exists as minimal unauthenticated endpoint | Keep detailed data on authenticated `/v1/*` surfaces |

---

## Phase 0 — Foundation

### Deliverable

A minimal stable foundation for the outward-facing pipeline.

### Build

#### 0-A — SQLite WAL Mode

Enable WAL mode for control plane DB connections used by the outward-facing pipeline.

#### 0-B — Startup Secret Validation

Add startup validation that rejects known placeholder values for outward-facing runtime secrets outside explicit local/dev mode. The minimum required check is `ORKET_API_KEY`; also validate any secret required by enabled `/v1/*` surfaces, such as encryption, session, or webhook secrets if those surfaces are enabled.

#### 0-C — Outward Run Event Store

Create `run_events` table and `LedgerEvent` model for new outward-facing pipeline events.

Required fields:

- `event_id`,
- `event_type`,
- `run_id`,
- `turn`,
- `agent_id`,
- `at`,
- `payload`,
- `event_hash` nullable until Phase 4,
- `chain_hash` nullable until Phase 4.

For v1, `payload` is the canonical outward-facing event payload and must be policy-safe by construction. Raw sensitive tool inputs, provider payloads, and internal artifacts stay outside `run_events.payload` unless an explicit run policy allows PII-bearing ledger payloads and the ledger/export is marked as containing PII.

Important scope limit: Phase 0 does **not** migrate all legacy observability, lifecycle, or run summary producers. New outward-facing run/proposal/decision/tool events must write to `run_events`. Legacy producers remain unchanged unless directly needed for the v1 loop.

#### 0-D — Minimal `/health`

Add unauthenticated:

```http
GET /health
```

Response:

```json
{ "status": "ok" }
```

Detailed counts belong in authenticated `/v1/stats`, not unauthenticated health.

#### 0-E — Version Header

Add `X-Orket-Version` to all `/v1/*` API responses.

#### 0-F — Auth Conformance

Verify the shared `/v1/*` authentication contract:

- `/v1/*` endpoints require `X-API-Key` unless explicitly exempted,
- API key comparison is timing-safe,
- authentication failures are logged without raw key values,
- `/health` remains unauthenticated and minimal.

#### 0-G — Minimal Outbound Policy Gate

Add the outbound policy gate as an enforced serialization boundary before any new operator-visible v1 payload surface ships. The Phase 0 gate may be a no-op by default, but call sites must already route through the gate so later policy hardening does not require retrofitting every API and CLI surface.

Add a reusable test helper or instrumentation point that proves a response path traversed the gate before serialization. Tests must not rely on the mere existence of the gate class.

Phase 0 does not implement full PII redaction, forbidden-pattern configuration, or field allowlist configuration.

#### 0-H — Minimal Built-In Connector Registry

Define the minimal built-in connector metadata registry required by later approval gating. The registry owns connector names and metadata shape for:

- `read_file`,
- `write_file`,
- `create_directory`,
- `delete_file`,
- `run_command`,
- `http_get`,
- `http_post`.

Connector `risk_level` values must use this vocabulary: `read`, `write`, `destructive`, `network`, or `command`.

The Phase 0 registry is metadata only. Full connector validation, invocation hardening, CLI inspection, harnesses, timeout behavior, HTTP allowlists, and third-party discovery remain out of scope.

### Done Condition

Phase 0 is done when:

1. tests pass for touched areas,
2. `/health` returns `status: ok`,
3. a store-level synthetic event write/read test proves `run_events` persistence without implying run submission exists,
4. placeholder outward-facing runtime secrets fail startup outside dev/local mode, including `ORKET_API_KEY` and any secret required by enabled `/v1/*` surfaces,
5. contract tests prove `/v1/*` auth requires `X-API-Key` unless explicitly exempted,
6. contract or unit tests prove timing-safe API key comparison,
7. contract tests prove auth failures are logged without raw key values,
8. concurrent DB write test does not hit `database is locked`,
9. `/v1/*` responses include `X-Orket-Version`,
10. the minimal outbound policy gate exists and at least one representative v1 response path proves, through a reusable test helper or instrumentation point, that it calls the gate before serialization,
11. the minimal built-in connector registry exposes the v1 connector metadata shape and stable risk vocabulary without implementing connector hardening.

### Do Not Start

- CLI commands,
- approval expansion,
- ledger export,
- SSE,
- policy redaction/configuration beyond the no-op gate boundary,
- connector hardening beyond the minimal metadata registry,
- migration of legacy event producers.

### Phase 0 Checkpoint

Phase 0 foundation implemented and verified on 2026-04-25. Proof used targeted integration, contract, and unit tests for minimal health, `/v1/*` auth conformance, version headers, startup secret checks, outbound policy gate traversal, synthetic `run_events` write/read and concurrent WAL writes, and connector metadata risk vocabulary.

---

## Phase 1 — Work Submission and Status

### Deliverable

An operator can submit work and query run status through API and CLI.

### Build

#### 1-A — Work Submission API

Update or add:

```http
POST /v1/runs
```

The endpoint must accept:

- optional `run_id`,
- optional `namespace`,
- required `task.description`,
- required `task.instruction`,
- optional `task.acceptance_contract`,
- optional `policy_overrides`.

It must be idempotent on `run_id`.

#### 1-B — Run Status API

Add or align:

```http
GET /v1/runs/{run_id}
```

Return the run status record required by the requirements document.

#### 1-C — Run List API

Add:

```http
GET /v1/runs
```

Support pagination and optional status filtering.

#### 1-D — CLI Skeleton

Add `orket` command with:

```bash
orket run submit --description "..." --instruction "..."
orket run status <run_id>
orket run list [--status active]
```

The CLI must use the API and contain no runtime business logic.

Suggested libraries:

- `typer` for CLI,
- `httpx` for HTTP.

#### 1-E — Policy Gate Call Sites

Route run submission, status, and list response payloads through the Phase 0 outbound policy gate before API serialization. CLI commands must display API-returned payloads rather than reimplementing policy behavior locally.

### Done Condition

Phase 1 is done when:

1. CLI submit prints a `run_id`,
2. CLI status returns the same run status as the API,
3. submitting the same `run_id` twice returns the same record,
4. missing `instruction` is rejected before execution,
5. run submission creates the expected initial `run_events` rows,
6. run submission, status, and list payloads pass through the outbound policy gate before serialization,
7. tests for run API and CLI pass.

### Do Not Start

- approvals CLI,
- event query endpoint,
- SSE,
- ledger export,
- policy redaction/configuration beyond the no-op gate boundary,
- connector discovery.

### Phase 1 Checkpoint

Phase 1 work submission and status implemented and verified on 2026-04-25. Proof used targeted integration, contract, and unit tests for `POST /v1/runs`, idempotent submission by `run_id`, missing-instruction rejection, `GET /v1/runs/{run_id}`, filtered `GET /v1/runs`, initial `run_submitted` ledger event creation, outbound policy gate traversal for submit/status/list payloads, and `orket run submit/status/list` API-client behavior.

---

## Phase 2 — Approval Surface

### Deliverable

An operator can review, approve, deny, or allow timeout of approval-required tool calls.

### Build

#### 2-A — Approval Queue

Add:

```http
GET /v1/approvals
```

Return pending proposals across active runs, sorted by `expires_at` ascending.

Approval queue and review payloads must pass through the outbound policy gate before serialization.

#### 2-B — Approval Decision APIs

Add:

```http
POST /v1/approvals/{proposal_id}/approve
POST /v1/approvals/{proposal_id}/deny
```

All decisions must be idempotent.

#### 2-C — Approval-Required Built-In Tools

Support approval gating for:

- `write_file`,
- `create_directory`,
- `delete_file`,
- `run_command`.

A gated tool must not produce its effect until approved.

Approval gating must read built-in tool names and metadata from the minimal connector registry created in Phase 0. Do not create a second approval-only tool registry.

#### 2-D — Timeout Auto-Deny

Add background timeout handling for pending proposals. Timeout emits `proposal_expired` or equivalent decision event with:

```text
operator_ref: system:timeout
reason: timeout_exceeded
```

For v1, timeout is terminal.

#### 2-E — Approval CLI

Add:

```bash
orket approvals list
orket approvals review <proposal_id>
orket approvals approve <proposal_id> [--note "..."]
orket approvals deny <proposal_id> --reason "..."
orket approvals watch
```

`review` must show proposal context and redacted args before prompting.

#### 2-F — Decision Events

Every approval, denial, and timeout must write a `run_events` row.

For v1, denial is terminal. Do not implement recovery-after-denial in this phase.
Approve-and-pause and pause-after-approval semantics are deferred from v1.

### Done Condition

Phase 2 is done when:

1. a run with `approval_required_tools: ["write_file"]` pauses before file write,
2. `orket approvals list` shows the proposal,
3. approving continues the run,
4. denying fails the run and records the reason,
5. timeout auto-denies and records `system:timeout`,
6. repeated decision calls return the original decision record,
7. no effect occurs before approval,
8. approval queue and review payloads pass through the outbound policy gate,
9. approval gating uses the Phase 0 connector registry as the tool metadata source,
10. no approve-and-pause endpoint, CLI command, ledger event, or pause-after-approval state exists,
11. tests for approval API, engine behavior, and CLI pass.

### Do Not Start

- SSE,
- ledger export,
- connector entry-point discovery,
- graphical UI,
- approve-and-pause semantics,
- recovery-after-denial semantics.

### Phase 2 Surface Checkpoint

Phase 2 outward approval surface checkpoint implemented and verified on 2026-04-25. This checkpoint adds persistent outward approval proposals, registry-backed approval metadata, pending review/list payloads, idempotent approve/deny decisions, terminal timeout denial, `proposal_pending_approval`, `proposal_approved`, `proposal_denied`, and `proposal_expired` `run_events` rows, API-client-only `orket approvals list/review/approve/deny/watch` commands, and outbound policy-gate traversal proof for approval list/review/decision payloads.

### Phase 2 Execution Checkpoint

Phase 2 outward execution integration implemented and verified on 2026-04-25. The first execution slice consumes one explicit `task.acceptance_contract.governed_tool_call`, starts the outward run, records `run_started`, `turn_started`, and `proposal_made`, pauses before an approval-required `write_file` effect, exposes the pending proposal through the approval queue, and applies the file write only after approval. Successful approval records `tool_invoked`, `commitment_recorded`, `turn_completed`, and `run_completed`; denial and timeout remain terminal and produce no effect.

This completes the Phase 2 done-condition proof for the `write_file` path. Broader connector effect support and hardening for `delete_file`, `run_command`, HTTP connectors, argument validation, allowlists, and timeout enforcement remain in Phase 5.

---

## Phase 3 — Run Inspection and Live Events

### Deliverable

An operator can inspect completed runs and watch active runs.

### Build

#### 3-A — Run Events API

Add:

```http
GET /v1/runs/{run_id}/events
```

Support filters:

- `from_turn`,
- `to_turn`,
- `types`,
- `agent_id`.

#### 3-B — Run Summary API

Add:

```http
GET /v1/runs/{run_id}/summary
```

Summary must be derived from persisted run records and `run_events`, not from presentation-only text.
Event and summary payloads must pass through the outbound policy gate before serialization.

#### 3-C — Live Event Stream

Add:

```http
GET /v1/runs/{run_id}/events/stream
```

Use SSE. Stream new `run_events` rows for the run. Close on terminal state. Emit heartbeat events as needed.

Implementation may use an in-process per-run queue for v1. If this is used, document that live streaming after process restart falls back to polling/events endpoint until a later durable pub/sub implementation exists.

SSE event payloads must pass through the outbound policy gate before they are emitted.

#### 3-D — CLI Inspection

Add:

```bash
orket run events <run_id> [--types proposal_made,proposal_approved] [--turn 3]
orket run summary <run_id>
orket run watch <run_id>
```

### Done Condition

Phase 3 is done when:

1. event endpoint returns ordered events for completed runs,
2. filters work,
3. summary counts match `run_events`,
4. live watch shows new events during an active run,
5. inspection endpoints do not alter event count, run state, or proposal state,
6. completed runs remain inspectable after process restart,
7. event, summary, and SSE payloads pass through the outbound policy gate,
8. tests for event API, summary API, and watch behavior pass.

### Do Not Start

- ledger export,
- connector SDK changes,
- new approval features,
- policy redaction/configuration beyond the no-op gate boundary,
- observability migration unrelated to `run_events`.

### Phase 3 Checkpoint

Phase 3 run inspection implemented and verified on 2026-04-25. This checkpoint adds filtered `GET /v1/runs/{run_id}/events`, derived `GET /v1/runs/{run_id}/summary`, polling-backed `GET /v1/runs/{run_id}/events/stream` with SSE framing, and API-client-only `orket run events/summary/watch` commands. Inspection reads persisted outward run records and `run_events`, routes event, summary, and stream payloads through the outbound policy gate, and does not mutate run state, event count, or proposal state.

The v1 live stream is process-local HTTP polling over the persisted `run_events` table and closes when the outward run is terminal. After process restart, operators can use the events endpoint for the same persisted event history; durable pub/sub remains deferred.

---

## Phase 4 — Ledger Export and Offline Verification

### Deliverable

An operator can export a run ledger and verify the export offline.

### Build

#### 4-A — Event Hashes and Chain Hashes

For events in `run_events`, compute:

- `event_hash` — SHA-256 of canonical JSON excluding `event_hash` and `chain_hash`,
- `chain_hash` — SHA-256 of the UTF-8 bytes of `previous_chain_hash + "\n" + event_hash`.

Canonical event order for a run is ascending `(run_id, turn, at, event_id)`. The first event uses `previous_chain_hash: "GENESIS"`.
Hashes are computed from the canonical outward-facing `run_events.payload` bytes. Full canonical exports must include those payload bytes unchanged. If outbound policy filtering must redact, omit, or transform already-recorded event payload bytes, the export is a partial disclosure view and must not be labeled or verified as the same full canonical ledger.

Backfill is allowed only for events already written to `run_events` by the outward-facing pipeline. Do not claim legacy pre-pipeline artifacts become canonical ledger events.

#### 4-B — Ledger Export Contract

Before Phase 4 runtime code starts, create a `ledger_export.v1` schema or contract document. It must define:

- full canonical export shape,
- filtered partial-view shape,
- `ledger_export_requested` event payload,
- `event_hash` and `chain_hash` fields,
- canonical ordering and genesis value,
- event group mapping, including `audit`,
- v1 policy-safe ledger payload and partial-disclosure rules,
- verification result vocabulary.

The export and verification implementation must follow this contract rather than allowing code to become the schema.

#### 4-C — Export API

Add:

```http
GET /v1/runs/{run_id}/ledger
```

Export must include:

- `schema_version`,
- `summary`,
- `policy_snapshot`,
- ordered events,
- `ledger_hash`.

Support filtering by event group as partial verified views. The unfiltered `all` export is the full canonical ledger only when exported event payload bytes are unchanged from `run_events.payload`. Filtered or redacted exports must identify themselves with `export_scope: "partial_view"`, include the canonical `ledger_hash`, include event positions for disclosed events, and include hash-chain anchors for omitted spans. They must not be represented as full canonical ledgers.

Event group mapping for v1:

- `proposals`: proposal events,
- `decisions`: approval, denial, and timeout decision events,
- `commitments`: commitment events,
- `tools`: governed tool invocation events,
- `audit`: `ledger_export_requested`,
- `all`: all v1 ledger events.

#### 4-D — Verify API

Add:

```http
GET /v1/runs/{run_id}/ledger/verify
```

This verifies the stored run events in the live instance.

#### 4-E — Offline Verify CLI

Add:

```bash
orket ledger export <run_id> --out <file.json>
orket ledger export <run_id> --types proposals,decisions --out <file.json>
orket ledger verify <file.json>
orket ledger summary <run_id>
```

`orket ledger verify <file.json>` must not require a running Orket instance.
For filtered partial views, offline verify must report partial-view validity, verify disclosed event hashes and disclosed chain links against the anchors, report the canonical ledger hash as the anchor target, and avoid claiming full-ledger completeness or omitted event payload verification.

#### 4-F — Default Export Policy Safety

Default export must pass through the outbound policy gate before serialization. For v1 full canonical exports, the gate should confirm that recorded ledger payloads are already policy-safe and leave event payload bytes unchanged. If the gate changes event payload bytes, the export becomes a partial disclosure view.

`--include-pii` must be explicit and recorded as a `ledger_export_requested` ledger event when requested through the live runtime.

The event payload must include `run_id`, `operator_ref`, `include_pii`, `export_scope`, `types`, and `requested_at`. It must be committed before the export response is serialized.
The event belongs to the `audit` event group and is included in `all` exports. It is excluded from `proposals`, `decisions`, `commitments`, and `tools` filtered exports unless `audit` is also requested.

### Done Condition

Phase 4 is done when:

1. export produces valid JSON,
2. offline verify returns valid for an unmodified full canonical ledger export using only exported event payload bytes,
3. filtered and redacted exports verify as partial views with canonical hash-chain anchors and do not claim full-ledger completeness,
4. offline verify returns invalid after one disclosed payload character is changed,
5. summary counts match event list,
6. default exports pass through the outbound policy gate without post-hash event payload mutation for full canonical exports,
7. any export that redacts already-recorded event payload bytes is marked and verified as a partial disclosure view,
8. `--include-pii` is explicit and records `ledger_export_requested` before export serialization,
9. `ledger_export_requested` follows the documented `audit` event group filtering behavior,
10. chain verification uses the documented canonical order and `GENESIS` value,
11. the `ledger_export.v1` schema or contract exists before export code is implemented,
12. legacy artifacts are not silently represented as canonical ledger events,
13. tests for export and offline verify pass.

### Do Not Start

- third-party connector discovery,
- graphical UI,
- legacy artifact import,
- alternate ledger authority for filtered exports,
- new governance docs except the required `ledger_export.v1` schema or contract.

---

### Phase 4 Checkpoint

Phase 4 ledger export and offline verification implemented and verified on 2026-04-25. The durable export contract lives at `docs/specs/LEDGER_EXPORT_V1.md` and defines `ledger_export.v1`, canonical `(run_id, turn, at, event_id)` ordering, `GENESIS`, event and chain hash formulas, full export semantics, partial verified views, omitted-span anchors, event group mapping, and the `ledger_export_requested` audit event.

Runtime implementation is application-owned by `orket/application/services/outward_ledger_service.py`, with pure hash and offline verification rules in `orket/core/domain/outward_ledger.py`. The outward `run_events` store backfills `event_hash` and `chain_hash` for outward pipeline events only; legacy artifacts are not promoted into canonical ledger events. The API exposes `GET /v1/runs/{run_id}/ledger` and `GET /v1/runs/{run_id}/ledger/verify`, and the CLI exposes API-backed `orket ledger export`, offline `orket ledger verify`, and API-backed `orket ledger summary`.

Default full exports pass through the outbound policy gate and preserve policy-safe event payload bytes for verification. Filtered exports are `partial_view` payloads with canonical `ledger_hash`, disclosed event positions, and omitted-span hash anchors. Explicit `include_pii=true` live exports append `ledger_export_requested` before response serialization, classify it as `audit`, include it in `all`, and exclude it from non-audit filtered groups.

---

## Phase 5 — Built-In Connector Hardening

### Deliverable

The built-in connector family is governed, validated, timeout-bound, and testable.

### Build

#### 5-A — Connector Metadata Shape

Harden the Phase 0 connector registry without creating a second connector authority. The built-in metadata shape remains:

- `name`,
- `description`,
- `args_schema`,
- `risk_level`,
- `pii_fields`,
- `timeout_seconds`.

`risk_level` must remain one of: `read`, `write`, `destructive`, `network`, or `command`.

This should be compatible with future SDK decorators, but do not implement third-party entry-point discovery in this phase.

#### 5-B — Built-In Connectors

Implement or align:

- `read_file`,
- `write_file`,
- `create_directory`,
- `delete_file`,
- `run_command`,
- `http_get`,
- `http_post`.

#### 5-C — Admission Validation

Validate args against schema before connector invocation. Invalid args must fail before side effect.

#### 5-D — Safety Enforcement

- File connectors enforce workspace path isolation.
- HTTP connectors enforce deployment allowlist.
- Runtime enforces connector timeout.

#### 5-E — Connector CLI

Add:

```bash
orket connectors list
orket connectors show <name>
orket connectors test <name> --args '{"path":"test.txt"}'
```

#### 5-F — Connector Test Harness

Add a harness that invokes a connector in isolation and returns the same ledger event field shape as a real invocation.

### Done Condition

Phase 5 is done when:

1. built-in connectors appear in `orket connectors list`,
2. invalid args are rejected before invocation,
3. path traversal is rejected before file effect,
4. non-allowlisted HTTP domain is rejected,
5. timeout produces `outcome: timeout`,
6. connector invocation writes the expected event shape,
7. connector hardening reuses the Phase 0 registry rather than creating a parallel tool authority,
8. connector metadata rejects risk levels outside the stable vocabulary,
9. connector harness output matches real invocation field names,
10. tests for built-in connectors and harness pass.

### Do Not Start

- third-party package discovery,
- connector versioning,
- marketplace/distribution tooling,
- multi-connector orchestration.

### Phase 5 Checkpoint

Phase 5 built-in connector hardening implemented and verified on 2026-04-25. This checkpoint keeps `orket/adapters/tools/registry.py::DEFAULT_BUILTIN_CONNECTOR_REGISTRY` as the single built-in connector metadata authority, adds schema validation before invocation, workspace path containment for file connectors, exact-host HTTP allowlist enforcement through `ORKET_CONNECTOR_HTTP_ALLOWLIST`, runtime timeout handling, local `orket connectors list/show/test` harness commands, and shared connector invocation ledger event fields: `connector_name`, `args_hash`, `result_summary`, `duration_ms`, and `outcome`.

Outward execution now uses the shared connector service after approval for registered governed connectors rather than the earlier Phase 2 write-only execution branch. Invalid connector args fail before proposal creation, rejected file paths create no file effect, non-allowlisted HTTP requests fail before constructing a network client, and timeout returns `outcome: timeout`. Third-party discovery, connector versioning, marketplace/distribution tooling, and multi-connector orchestration remain deferred.

---

## Phase 6 — Outbound Policy Gate Hardening

### Deliverable

The already-enforced outbound policy gate is hardened with real redaction and configuration behavior.

### Build

#### 6-A — Policy Gate Hardening

Harden the Phase 0 pure outbound policy gate:

```python
@dataclass(frozen=True)
class OutboundPolicyGate:
    pii_field_paths: list[str]
    forbidden_patterns: list[str]
    allowed_output_fields: dict[str, list[str]]

    def filter(self, event_type: str, payload: dict) -> dict:
        """Return a scrubbed copy. Do not mutate input."""
```

#### 6-B — Verify Operator-Visible Surfaces

Verify the existing gate call sites cover:

- approval queue responses,
- approval review responses,
- run event inspection,
- run summary where event payloads are surfaced,
- default ledger export.

#### 6-C — Configuration

Support environment and config-file configuration for:

- PII field paths,
- forbidden regex patterns,
- allowed output fields by event type.

### Done Condition

Phase 6 is done when:

1. configured PII field is redacted in approval payloads,
2. forbidden pattern is filtered in event/summary/export payloads,
3. gate is deterministic for the same input,
4. gate never mutates input payload,
5. default ledger export preserves the same policy-safe full-export or partial-disclosure behavior,
6. existing operator-visible call sites still route through the gate after hardening,
7. tests for outbound policy gate pass.

### Do Not Start

- new approval features,
- UI,
- connector marketplace,
- first-time policy-gate wiring that should have happened in earlier phases,
- policy authoring UI.

### Phase 6 Checkpoint

Phase 6 outbound policy gate hardening implemented and verified on 2026-04-25. This checkpoint adds the `OutboundPolicyGate` dataclass with configured PII field-path redaction, forbidden regex pattern filtering, allowed output fields by event/surface type, deterministic pure filtering, and non-mutating payload handling while preserving the existing `apply_outbound_policy_gate()` call surface.

Configuration is supported through environment variables and an optional JSON config file referenced by `ORKET_OUTBOUND_POLICY_CONFIG_PATH`. API startup loads the config file once, and per-response filtering remains pure. Supported environment keys are `ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS`, `ORKET_OUTBOUND_POLICY_FORBIDDEN_PATTERNS`, and `ORKET_OUTBOUND_POLICY_ALLOWED_OUTPUT_FIELDS`.

Approval queue payloads, run event inspection, run summaries, and default ledger exports were verified through existing operator-visible gate call sites. When a configured policy would redact stored ledger event payload bytes from a full export, the outbound gate now returns a `partial_view` with omitted-span hash anchors rather than a false full canonical ledger.

---

## Deferred Backlog

| Item | Reason Deferred |
|---|---|
| Graphical web UI | CLI proves v1 pipeline first |
| Third-party connector entry-point discovery | Built-in connector governance must be proven first |
| Connector versioning | Not required for first complete loop |
| Multi-operator identity and roles | Single operator key is sufficient for v1 |
| Recovery-after-denial | Adds policy ambiguity; v1 denial is terminal |
| Approve-and-pause | Adds pause-state policy ambiguity; defer until state transitions and ledger events are specified |
| Run cancellation | Mid-turn cancellation semantics need separate design |
| Legacy artifact import | Could create false authority; requires explicit future contract |
| Model benchmark surfaces | Not part of outward-facing governance path |
| Prompt reforging surfaces | Not part of outward-facing governance path |
| Internal governance migration | Would point the pipeline inward again |
| Durable SSE pub/sub | In-process live stream is acceptable for v1 |

---

## End-to-End Acceptance Tests

By the end of Phase 6, these tests must pass.

### Test 1 — Approval Path

```text
Submit task
→ agent calls write_file
→ proposal appears
→ operator approves
→ effect occurs
→ run completes or reaches expected terminal state
→ export ledger
→ offline verify succeeds
```

### Test 2 — Denial Path

```text
Submit task
→ agent calls write_file
→ proposal appears
→ operator denies with reason
→ no effect occurs
→ run fails
→ denial reason appears in ledger
→ offline verify succeeds
```

### Test 3 — Timeout Path

```text
Submit task with approval_timeout_seconds=10
→ agent calls approval-required tool
→ operator takes no action
→ timeout auto-denies
→ no effect occurs
→ run fails
→ ledger records system timeout
→ offline verify succeeds
```

---

## Success Condition

The plan succeeds when an operator can complete the first outward-facing governed run loop without reading internal Orket governance documentation:

```text
submit → review → decide → inspect → export → verify
```

---

### End-to-End Acceptance Checkpoint

End-to-end acceptance implemented and verified on 2026-04-25. Proof covers the approval, denial, and timeout paths through the outward API with real SQLite persistence, real workspace file effects or effect absence, run inspection, ledger export, and offline `ledger_export.v1` verification.

Observed paths:

- approval path: `primary`, result `success`;
- denial path: `primary`, result `success`;
- timeout path: `primary`, result `success`.

---

*End of Implementation Plan*
