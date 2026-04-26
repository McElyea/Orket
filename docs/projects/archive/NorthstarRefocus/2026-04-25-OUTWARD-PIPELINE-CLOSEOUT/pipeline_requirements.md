# Orket — Outward-Facing Pipeline Requirements
*Version 1.1 · April 25, 2026*

---

## Purpose

This document defines the required outward-facing operator surfaces for Orket v1.

It covers the path from work submission to approval, inspection, ledger export, and connector execution. It does not govern Orket's internal development process, internal proof lanes, CI/CD policy, benchmark tooling, or future UI design.

Canonical documents for this lane are `north_star.md`, `pipeline_requirements.md`, and `implementation_plan.md`. The durable Phase 4 ledger export contract is `docs/specs/LEDGER_EXPORT_V1.md`. Draft filenames with `_revised` are not part of the accepted authority set.

---

## Governed Pipeline

```text
Work submission
→ run execution
→ proposal review when required
→ operator decision
→ committed event record
→ ledger export and verification
```

The v1 operator-facing pipeline has five required surfaces:

1. Work Submission
2. Run Inspection
3. Proposal Review and Approval
4. Ledger Export and Verification
5. Connector Execution

The CLI and REST API must expose the same underlying records. The CLI may format results for humans, but it must not contain business logic that changes runtime behavior.

---

## Definitions

| Term | Meaning |
|---|---|
| Operator | Human or system controlling an Orket instance |
| Agent | AI-driven process running inside Orket |
| Run | One governed execution from submission to terminal state |
| Namespace | Scope boundary for a run; default is `issue:<run_id>` |
| Proposal | Agent-generated content, tool call, or state change before commitment |
| Governed tool | Tool whose invocation passes through admission and, when configured, approval |
| Approval-required tool | Governed tool that pauses for operator decision before effect |
| Commitment | Proposal that has passed required gates and has been recorded |
| Ledger event | Canonical event written to the outward-facing run event store |
| Ledger export | Portable JSON document containing run summary, policy snapshot, events, and integrity hashes |

---

## Shared Requirements

**REQ-SH-01** — All `/v1/*` API endpoints MUST require authentication using `X-API-Key` unless explicitly exempted.

**REQ-SH-02** — API key checks MUST use timing-safe comparison.

**REQ-SH-03** — Authentication failures MUST be logged without storing the raw key.

**REQ-SH-04** — Startup MUST validate outward-facing runtime secrets, including `ORKET_API_KEY` and any secret required by enabled `/v1/*` surfaces. Known placeholder values MUST be rejected outside explicit local/dev mode.

**REQ-SH-05** — Every API response under `/v1/*` MUST include `X-Orket-Version`.

**REQ-SH-06** — `GET /health` MUST be unauthenticated and return only minimal health information by default:

```json
{ "status": "ok" }
```

**REQ-SH-07** — Detailed runtime statistics MUST be exposed only through authenticated `/v1/stats`.

**REQ-SH-08** — Operator-visible payloads MUST pass through the outbound policy gate before serialization. This requirement is effective for the first new v1 operator-visible surface and MUST NOT wait for later policy-gate hardening.

**REQ-SH-09** — Inspection endpoints MUST be read-only. Calling them MUST NOT alter run state, event count, ledger hash, or proposal state.

### Shared Acceptance Criteria

- Contract test: unauthenticated requests to `/v1/*` endpoints are rejected unless the endpoint is explicitly exempted.
- Contract test: invalid API keys are rejected through timing-safe comparison.
- Contract test: authentication failures are logged without the raw key value.
- Contract test: `/health` remains unauthenticated and returns only `{ "status": "ok" }` by default.
- Contract test: the first new operator-visible API and CLI payloads pass through the outbound policy gate before serialization, even when the gate is configured as a no-op.
- Test helpers can prove a response path traversed the outbound policy gate, not merely that the gate class exists.

---

## Surface 1 — Work Submission

### Purpose

Operators submit a unit of work and receive a stable run record.

### Functional Requirements

**REQ-WS-01** — Work submission MUST assign or accept a stable `run_id` before execution begins.

**REQ-WS-02** — Work submission MUST accept an optional `namespace`. If omitted, Orket MUST assign `issue:<run_id>`.

**REQ-WS-03** — Work submission MUST accept a `task` object with:

- `description` — string, required,
- `instruction` — string, required,
- `acceptance_contract` — object, optional.

**REQ-WS-04** — Work submission MUST accept `policy_overrides` with:

- `approval_required_tools` — list of tool names,
- `max_turns` — integer,
- `approval_timeout_seconds` — integer.

**REQ-WS-05** — Submission MUST be idempotent on `run_id`. Re-submitting the same `run_id` MUST return the existing run record.

**REQ-WS-06** — Submission MUST reject invalid input before execution begins.

**REQ-WS-07** — Submission MUST reject namespace conflicts for active runs.

**REQ-WS-08** — Submission MUST be available through REST API and CLI.

For the Phase 2 execution slice, `task.acceptance_contract` MAY include one explicit governed tool proposal:

```json
{
  "governed_tool_call": {
    "tool": "write_file",
    "args": { "path": "approved.txt", "content": "approved content" }
  }
}
```

When this field is absent, submission creates a queued run record but does not imply execution has started. When this field is present, the v1 outward execution slice treats it as the agent's explicit proposed governed tool call and applies approval gating before any effect.

### API Contract

```http
POST /v1/runs
Content-Type: application/json
```

```json
{
  "run_id": "optional-operator-id",
  "namespace": "optional-namespace",
  "task": {
    "description": "Write a function that parses CSV files",
    "instruction": "Implement and test the parser",
    "acceptance_contract": {}
  },
  "policy_overrides": {
    "approval_required_tools": ["write_file"],
    "max_turns": 20,
    "approval_timeout_seconds": 300
  }
}
```

Response:

```json
{
  "run_id": "run-a1b2c3d4",
  "status": "queued",
  "namespace": "issue:run-a1b2c3d4",
  "submitted_at": "2026-04-25T12:00:00Z"
}
```

### CLI Contract

```bash
orket run submit \
  --description "Write a function that parses CSV files" \
  --instruction-file task.txt \
  --approval-required-tools write_file \
  --max-turns 20
```

### Acceptance Criteria

- Valid submission returns a stable `run_id`.
- Re-submitting the same `run_id` returns the same record.
- Missing `instruction` is rejected with a descriptive error.
- CLI and API produce equivalent run records.

---

## Surface 2 — Run Inspection

### Purpose

Operators inspect active and completed runs without changing them.

### Functional Requirements

**REQ-RI-01** — Orket MUST expose run status for any known `run_id`.

**REQ-RI-02** — Status MUST include:

- `run_id`,
- `status`,
- `current_turn`,
- `max_turns`,
- `started_at`,
- `completed_at`,
- `stop_reason`,
- `pending_proposals`.

**REQ-RI-03** — Orket MUST expose ordered run events for a run.

**REQ-RI-04** — Events MUST be filterable by turn range, event type, and agent ID.

**REQ-RI-05** — Orket MUST expose live run observation through Server-Sent Events.

**REQ-RI-06** — Orket MUST expose a structured run summary for completed runs.

**REQ-RI-07** — Completed runs MUST remain inspectable from persisted records until explicitly pruned by a future retention policy.

### Event Types for v1

| Event Type | Meaning |
|---|---|
| `run_submitted` | Work submission is accepted and assigned a stable run id |
| `run_started` | Run becomes active |
| `turn_started` | Agent turn begins |
| `proposal_made` | Agent produces a proposal |
| `proposal_admitted` | Admission gate accepts proposal |
| `proposal_rejected_gate` | Admission gate rejects proposal |
| `proposal_pending_approval` | Proposal requires operator decision |
| `proposal_approved` | Operator approves proposal |
| `proposal_denied` | Operator denies proposal |
| `proposal_expired` | Proposal times out |
| `commitment_recorded` | Proposal is committed |
| `tool_invoked` | Governed tool executes |
| `ledger_export_requested` | Operator requests a live-runtime ledger export; required when PII is included |
| `turn_completed` | Agent turn ends |
| `run_completed` | Run completes successfully |
| `run_failed` | Run reaches failure state |

### API Contract

```http
GET /v1/runs/{run_id}
GET /v1/runs/{run_id}/events?from_turn=0&types=proposal_made,proposal_approved
GET /v1/runs/{run_id}/events/stream
GET /v1/runs/{run_id}/summary
GET /v1/stats
```

### CLI Contract

```bash
orket run status <run_id>
orket run list [--status active]
orket run events <run_id> [--types proposal_made,proposal_approved]
orket run watch <run_id>
orket run summary <run_id>
```

### Acceptance Criteria

- Status endpoint returns current status for active and completed runs.
- Event endpoint returns events in deterministic order.
- Filtering by type and turn range works.
- SSE delivers new events during an active run.
- Inspection calls produce no state changes.
- Persisted completed runs are inspectable after restart.

---

## Surface 3 — Proposal Review and Approval

### Purpose

Approval-required tools pause before effect and require an operator decision.

### Functional Requirements

**REQ-PA-01** — A governed tool configured as approval-required MUST emit `proposal_pending_approval` before any effect occurs.

**REQ-PA-02** — A pending proposal MUST include:

- `proposal_id`,
- `run_id`,
- `namespace`,
- `tool`,
- redacted `args_preview`,
- `context_summary`,
- `risk_level`,
- `submitted_at`,
- `expires_at`.

**REQ-PA-03** — Operators MUST be able to approve or deny a pending proposal.

**REQ-PA-04** — For v1, denial is terminal. A denied proposal causes the run to fail with the denial reason recorded.

**REQ-PA-05** — Approve-and-pause and pause-after-approval policy semantics are deferred from v1. V1 approval resumes execution according to the current run policy and does not introduce a new pause state.

**REQ-PA-06** — Approval decisions MUST be idempotent. Repeating a decision request for the same `proposal_id` MUST return the original decision record.

**REQ-PA-07** — Approval timeout MUST auto-deny with `operator_ref: "system:timeout"` and `reason: "timeout_exceeded"`.

**REQ-PA-08** — Approval, denial, and timeout MUST be ledger events.

**REQ-PA-09** — The v1 built-in approval-required tool family MUST be registered through the minimal built-in connector registry before approval gating is generalized:

- `write_file`,
- `create_directory`,
- `delete_file`,
- `run_command`.

**REQ-PA-10** — Additional tools may be configured through `approval_required_tools` only if they are registered governed connectors.

### API Contract

```http
GET /v1/approvals
POST /v1/approvals/{proposal_id}/approve
POST /v1/approvals/{proposal_id}/deny
```

### CLI Contract

```bash
orket approvals list
orket approvals review <proposal_id>
orket approvals approve <proposal_id> [--note "..."]
orket approvals deny <proposal_id> --reason "..."
orket approvals watch
```

The interactive review command MUST display proposal context before prompting for a decision.

### Acceptance Criteria

- Approval-required tool call appears in the approval queue before effect.
- Approving continues the run.
- Denying fails the run and records the reason.
- Timeout auto-denies and records `system:timeout`.
- Repeated approval/denial calls return the original decision record.
- CLI review displays context and redacted args before decision.
- No approve-and-pause endpoint, CLI command, ledger event, or pause-after-approval state is part of v1.

---

## Surface 4 — Ledger Export and Verification

### Purpose

Operators export a portable record of a run and verify that the exported event sequence has not been altered.

### Functional Requirements

**REQ-LE-01** — Orket MUST export a completed or terminal run ledger as JSON.

**REQ-LE-02** — Export MUST include:

- `schema_version`,
- `summary`,
- `policy_snapshot`,
- ordered `events`,
- `ledger_hash`.

**REQ-LE-03** — Each event MUST include `event_hash`.

**REQ-LE-04** — Exported events MUST include a hash chain by `chain_hash`. Events are chained in ascending `(run_id, turn, at, event_id)` order. The first event uses `previous_chain_hash: "GENESIS"`. Each `chain_hash` is computed from the UTF-8 bytes of `previous_chain_hash + "\n" + event_hash`.

**REQ-LE-05** — Offline verification MUST recompute event hashes and chain hash from the event payload bytes present in the export file.

**REQ-LE-06** — Operator decisions MUST appear as first-class events.

**REQ-LE-07** — For v1, `run_events.payload` is the canonical outward-facing event payload and MUST be policy-safe by construction. Raw sensitive tool inputs, provider payloads, or internal artifacts MUST NOT be stored in `run_events.payload` unless the run policy explicitly allows PII-bearing ledger payloads and the resulting ledger/export is marked as containing PII. Raw/internal artifacts that are not policy-safe belong outside `ledger_export.v1`.

**REQ-LE-08** — A full canonical ledger export MUST NOT alter event payload fields after `event_hash` and `chain_hash` are computed. If outbound policy filtering would redact, omit, or transform event payload bytes, the export MUST be represented as a partial disclosure view, not as the same full canonical ledger.

**REQ-LE-09** — Export MUST support a full canonical ledger export and filtered event-group views for `proposals`, `decisions`, `commitments`, `tools`, `audit`, or `all`.

**REQ-LE-10** — The unfiltered `all` export is the full canonical ledger only when event payloads are exported exactly as recorded. Filtered exports and redacted disclosure exports are partial verified views, not full canonical ledgers.

**REQ-LE-11** — A filtered or redacted partial view MUST include `export_scope: "partial_view"`, the canonical `ledger_hash`, included event positions, and hash-chain anchors for omitted spans. Offline verification of a partial view MUST verify disclosed event hashes and disclosed chain links against the included anchors, report the canonical ledger hash as the anchor target, and avoid claiming full-ledger completeness or omitted-payload verification.

**REQ-LE-12** — Default exports MUST be policy-safe. For v1, this is achieved primarily by writing only policy-safe payloads to `run_events.payload`. If a default export must redact already-recorded event payload bytes, it MUST be a partial disclosure view.

**REQ-LE-13** — `--include-pii` MUST be explicit and MUST be recorded as a `ledger_export_requested` ledger event when invoked through a running Orket instance. The event MUST be committed before the export response is serialized.

The `ledger_export_requested` payload MUST include:

```json
{
  "run_id": "run-a1b2c3d4",
  "operator_ref": "operator:local",
  "include_pii": true,
  "export_scope": "all",
  "types": ["all"],
  "requested_at": "2026-04-25T12:00:00Z"
}
```

**REQ-LE-14** — `ledger_export_requested` belongs to the `audit` event group. It is included in `all` exports and in `types=audit` filtered exports; it is excluded from `proposals`, `decisions`, `commitments`, and `tools` filtered exports unless the caller also requests `audit`.

**REQ-LE-15** — `schema_version` MUST be `ledger_export.v1` for this requirements version.

**REQ-LE-16** — Legacy artifacts created before this pipeline are not automatically canonical ledger events. They may be referenced as historical artifacts only if imported by a future explicit import process.

**REQ-LE-17** — Phase 4 implementation MUST be preceded by a `ledger_export.v1` schema or contract document that defines the full export shape, partial-view shape, hash fields, canonical ordering, genesis value, event group mapping, PII/disclosure model, and verification result vocabulary. The code MUST implement that contract rather than becoming the contract.

### API Contract

```http
GET /v1/runs/{run_id}/ledger
GET /v1/runs/{run_id}/ledger?types=proposals,decisions
GET /v1/runs/{run_id}/ledger/verify
```

### CLI Contract

```bash
orket ledger export <run_id> --out run_ledger.json
orket ledger export <run_id> --types proposals,decisions --out decisions.json
orket ledger verify run_ledger.json
orket ledger summary <run_id>
```

### Acceptance Criteria

- Ledger export produces parseable JSON.
- Offline verification returns valid for an unmodified full canonical ledger export whose event payload bytes match the recorded canonical payloads.
- Offline verification returns valid for an unmodified filtered or redacted partial view while clearly reporting it as a partial view.
- Offline verification fails after mutating one disclosed event payload in either a full export or filtered partial view.
- Summary counts match exported events for a full export and disclosed events for a partial view.
- Default full exports verify from the exported event payload bytes and do not rely on hidden raw payload bytes.
- If policy filtering changes event payload bytes, the export is marked and verified as a partial disclosure view, not a full canonical ledger.
- Export does not require a running Orket instance to verify.
- Filtered exports include canonical hash-chain anchors and are not represented as full canonical ledgers.
- A live-runtime export using `--include-pii` records `ledger_export_requested` in the ledger before serialization.
- `ledger_export_requested` is included in `all` and `audit` exports, and excluded from other filtered groups unless `audit` is requested.
- A ledger export schema or contract exists before Phase 4 code is implemented.

---

## Surface 5 — Connector Execution

### Purpose

Connectors bring external tools and APIs into the governed runtime without bypassing admission, approval, timeout, policy, or ledger recording.

### v1 Scope

The first v1 scope is built-in connector hardening. Third-party connector discovery is valuable but should not block the first complete outward-facing pipeline.

The minimal built-in connector metadata registry is a foundation requirement for approval gating. Full connector hardening, CLI inspection, test harnesses, HTTP allowlist enforcement, timeout enforcement, and third-party discovery remain part of the later connector phase.

### Functional Requirements

**REQ-CS-01** — Built-in connectors MUST be registered through one minimal connector metadata registry before approval-gated built-in tools are generalized. The registry MUST be the single source used by approval gating and later connector hardening.

**REQ-CS-02** — Connector metadata MUST include:

- `name`,
- `description`,
- `args_schema`,
- `risk_level`,
- `pii_fields`,
- `timeout_seconds`.

`risk_level` MUST be one of:

- `read`,
- `write`,
- `destructive`,
- `network`,
- `command`.

**REQ-CS-03** — Connector arguments MUST be validated against `args_schema` before invocation.

**REQ-CS-04** — Invalid arguments MUST be rejected with field-level details and no connector side effect.

**REQ-CS-05** — Connector timeout MUST be enforced by the runtime.

**REQ-CS-06** — Connector invocation MUST emit a ledger event with:

- `connector_name`,
- `args_hash`,
- `result_summary`,
- `duration_ms`,
- `outcome`.

**REQ-CS-07** — Built-in v1 connectors are:

- `read_file`,
- `write_file`,
- `create_directory`,
- `delete_file`,
- `run_command`,
- `http_get`,
- `http_post`.

**REQ-CS-08** — Workspace file connectors MUST reject path traversal before invocation.

**REQ-CS-09** — HTTP connectors MUST require a deployment allowlist.

**REQ-CS-10** — Connector test harness MUST invoke a connector in isolation and return the ledger event shape that a real invocation would produce.

### Deferred Connector Requirements

The following are deferred until after the built-in connector path is proven:

- third-party package entry-point discovery,
- connector versioning,
- connector distribution or marketplace tooling,
- multi-connector orchestration features.

### CLI Contract

```bash
orket connectors list
orket connectors show <name>
orket connectors test <name> --args '{"path":"test.txt"}'
```

### Acceptance Criteria

- Built-in connectors are listed by the CLI.
- Invalid args are rejected before connector invocation.
- Path traversal is rejected before file effect.
- Non-allowlisted HTTP domain is rejected.
- Timeout produces `outcome: timeout`.
- Test harness returns the same event field shape as a real invocation.

---

## Outbound Policy Gate

### Purpose

The outbound policy gate prevents sensitive or forbidden content from being shown to operators or included in default exports.

### Functional Requirements

**REQ-OPG-01** — A minimal outbound policy gate MUST exist before any new operator-visible v1 surface ships. It MAY be configured as a no-op by default until hardening is implemented.

**REQ-OPG-02** — Every new operator-visible payload surface MUST call the outbound policy gate before serialization.

**REQ-OPG-03** — The outbound policy gate MUST be a pure function over event type and payload.

**REQ-OPG-04** — It MUST support PII field path redaction.

**REQ-OPG-05** — It MUST support forbidden regex pattern filtering.

**REQ-OPG-06** — It MUST support allowed output fields per event type.

**REQ-OPG-07** — It MUST be applied to approval payloads, event inspection payloads, summaries, and default ledger exports.

**REQ-OPG-08** — It MUST never mutate its input payload.

**REQ-OPG-09** — Tests MUST be able to prove a response path passed through the outbound policy gate before serialization. Existence of the gate object alone is not sufficient proof.

---

## Explicit Non-Requirements for v1

The following are out of scope:

1. Graphical web UI.
2. Multi-tenant accounts or role-based approval.
3. Cloud-hosted Orket service.
4. Benchmarking/model-selection as operator-facing functionality.
5. Prompt reforging as operator-facing functionality.
6. Internal governance documentation surfaces.
7. Recovery-after-denial semantics.
8. Third-party connector marketplace or distribution tooling.
9. Retrofitting legacy artifacts into canonical ledger events.
10. Migrating Orket's internal development process onto this outward-facing pipeline.
11. Approve-and-pause or pause-after-approval workflow semantics.

---

## End-to-End v1 Acceptance Tests

### Test 1 — Approval Path

```text
Submit task
→ agent calls write_file
→ proposal appears
→ operator approves
→ run continues
→ ledger exports
→ offline verify succeeds
```

### Test 2 — Denial Path

```text
Submit task
→ agent calls write_file
→ proposal appears
→ operator denies with reason
→ run fails
→ denial reason appears in ledger
→ offline verify succeeds
```

### Test 3 — Timeout Path

```text
Submit task with approval_timeout_seconds=10
→ agent calls governed tool
→ operator does nothing
→ proposal expires
→ run fails
→ ledger records system timeout
→ offline verify succeeds
```

---

*End of Requirements*
