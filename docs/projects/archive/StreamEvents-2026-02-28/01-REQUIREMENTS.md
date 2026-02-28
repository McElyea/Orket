# Stream Events Requirements (v1)

## Scope
Define a streaming interaction architecture for game/NPC workflows that preserves Orket deterministic governance for authoritative world-state commits.

## Problem Statement
- NPC interactions must feel immediate for players.
- Local model startup/switch latency is unavoidable.
- World truth must remain deterministic and auditable.

## Core Architecture Rule
- Orket shall implement two distinct runtime planes:
- Interaction Plane: streaming-first, low-latency, non-authoritative.
- Authority Plane: deterministic, fail-closed, authoritative commits at lifecycle boundaries.

## Functional Requirements

### R0: Event Envelope, Ordering, and Timestamp Sources
- Every stream event shall include:
- `schema_v`
- `session_id`
- `turn_id`
- `seq`
- `mono_ts_ms`
- `event_type`
- `payload`
- `seq` shall be strictly increasing per (`session_id`, `turn_id`) with no duplicates.
- Event ordering shall use (`session_id`, `turn_id`, `seq`) only.
- Ordering shall never be based on timestamps.
- `turn_id` shall be unique within `session_id`.
- `turn_id` shall never be reused, including after cancellation/failure/retry.
- `commit_final` is part of the same stream and uses the same (`session_id`, `turn_id`, `seq`) ordering domain.
- `commit_final` shall have greater `seq` than the terminal interaction-plane turn event for the same turn.
- `mono_ts_ms` is required and shall come from a monotonic clock source.
- `wall_ts` is optional for human logs/correlation only.
- `seq` gaps are forbidden unless event payload includes `dropped_seq_ranges`.
- `dropped_seq_ranges` shall be a sorted ascending list of non-overlapping inclusive ranges:
- `{ "start_seq": <int>, "end_seq": <int> }`
- If `dropped_seq_ranges` is present, client shall treat missing seq values in those ranges as intentionally dropped best-effort events, not transport failure.

### R1: Interaction Plane Events (Streaming)
- System shall stream interaction events for each turn/session:
- `turn_accepted`
- `model_selected`
- `model_loading`
- `model_ready`
- `token_delta` (or chunk delta)
- `tool_call_started`
- `tool_call_result`
- `turn_interrupted` (when canceled)
- `turn_final` (interaction-plane final payload, explicitly non-authoritative)

### R1b: Two-Phase Final
- `turn_final` shall be interaction-plane only and non-authoritative.
- `commit_final` shall be authority-plane only and emitted only after authority boundary evaluation completes.
- `commit_final.payload` shall include:
- `authoritative: true` (required constant)
- `commit_digest` (required deterministic digest for authority result boundary)
- `commit_id` (optional)
- `commit_outcome: "ok" | "fail_closed"` (required)
- `issues[]` (required, may be empty)
- `artifact_refs[]` (required, may be empty)

### R2: Authority Plane Commit Boundaries
- Authoritative world-state mutation shall occur only at explicit boundaries:
- end of turn finalization
- validated tool result boundary
- approved decision/score boundary
- Partial streamed tokens/events shall never directly mutate world truth.

### R3: Cancellation/Interruptibility
- Interaction sessions shall support cancellation while generation is in progress.
- Interrupts shall emit deterministic stop events and avoid partial-state commits.
- Cancel request shall produce exactly one terminal turn event:
- either `turn_interrupted` or `turn_final` (never both).
- Cancel requests received after `turn_final` shall be no-op and shall not alter authority commit in progress.
- A terminal turn event is one of: `turn_interrupted`, `turn_final`.
- After terminal turn event emission for (`session_id`, `turn_id`), no further events for that turn may be emitted except `commit_final`.

### R3c: Tool Cancellation Default
- Default behavior for cancel during tool execution is finish-then-discard:
- running tool may finish
- `tool_call_result` may still be emitted with `canceled=true`
- authority path shall discard tool authority impact unless tool declares `cancel_safe=true` and cancellation occurred before side effects.
- Tools may opt into safe cancellation only with declared side-effect semantics.
- Tool event payload requirements:
- `tool_call_started` payload shall include `tool_call_id` (unique within turn) and `tool_name`.
- `tool_call_result` payload shall include `tool_call_id`, `tool_name`, and `canceled`.
- If `canceled=true`, `tool_call_result` payload shall include `side_effects_may_have_occurred` (boolean, required).

### R4: Reliable Mode Compatibility
- Existing Reliable Mode governance shall remain authoritative for commit paths.
- Streaming events shall be treated as telemetry/interaction artifacts unless finalized by authority boundary logic.

### R5: Model Switch Transparency
- Runtime shall emit explicit model lifecycle events so clients never block silently during model selection/loading/switching.
- Event stream shall acknowledge user input immediately without waiting for model readiness.
- `model_selected` payload shall include `model_id` and `reason`.
- `model_loading` payload shall include `cold_start` and optional `progress` (`0.0..1.0`).
- `model_ready` payload shall include `model_id`, `warm_state` (`hot|warm|cold`), and `load_ms`.

### R6: Extension Compatibility
- Stream interaction flow shall integrate with ExtensionManager workloads without direct DecisionNodeRegistry wiring by extension authors.
- Public extension contract remains `ExtensionManager + Workload`.

### R6b: Extension Participation Seam
- `ExtensionManager + Workload` shall receive `InteractionContext` with:
- `emit_event(event: StreamEvent)`
- `request_commit(intent)`
- `is_canceled()`
- `await_cancel()`
- `StreamEvent.event_type` must be from declared v1 event enum.
- Extension-specific event data is allowed only under `payload.ext`.
- `payload.ext` shall contain `namespace` and `data`.
- `namespace` shall be prefixed form `ext.<publisher>.<extension>`.
- `request_commit(intent)` minimum contract:
- `intent.type` (enum: `tool_result`, `decision`, `turn_finalize`)
- `intent.ref` (opaque string correlation id)
- `intent.payload_digest` (optional)

### R7: Session API Surface
- Introduce an explicit `InteractionSession` runtime abstraction with:
- `start(session_params) -> session_id`
- `begin_turn(input, turn_params) -> turn_id` (must emit `turn_accepted` immediately)
- `subscribe(transport) -> stream`
- `cancel(turn_id | session_id)`
- `finalize(turn_id) -> CommitHandle`
- `close(session_id)`
- Turns are linear by default per session unless explicitly declared concurrent.

### R8: Deterministic Auditability
- Turn finalization shall produce deterministic authoritative artifacts/provenance.
- Streaming traces may be retained but must be clearly marked non-authoritative.

### R8b: Artifact Labeling
- Interaction stream traces shall be stored as trace artifacts (for example `interaction_trace.jsonl`) and include `authoritative=false`.
- Authority artifacts shall include `authoritative=true` and remain canonical source of truth for replay/audit.

### R9: Performance Targets (Initial)
- Input receipt to `turn_accepted`: target <= 50 ms on local runtime path.
- Model-loading visibility event emitted immediately when loading begins.
- Backpressure handling shall avoid unbounded queue growth.

### R9b: Backpressure Policy
- Event classes:
- `must_deliver`: `turn_accepted`, `turn_interrupted`, `turn_final`, `commit_final`
- `best_effort`: `token_delta`, progress/model load progress deltas
- `bounded`: tool lifecycle events
- If best-effort queue exceeds capacity:
- server may coalesce token deltas
- server may drop intermediate deltas
- server shall still deliver `turn_final` and `commit_final`
- Runtime shall expose configurable queue limits:
- `best_effort_max_events_per_turn`
- `bounded_max_events_per_turn`
- `max_bytes_per_turn_queue`
- When limits are exceeded, runtime shall apply drop/coalesce policy and emit `dropped_seq_ranges`.

## Non-Goals (v1)
- Global distributed multi-node stream federation.
- Cross-process transactional consensus for authority commits.
- Full QoS guarantees for every telemetry event.

## Acceptance Criteria
1. Client receives immediate `turn_accepted` and subsequent lifecycle events over streaming transport.
2. Cancel operation stops in-flight generation and emits deterministic interruption event.
3. No world-state mutation occurs from partial streamed output.
4. Finalized turn commits through authoritative path with provenance and fail-closed behavior.
5. `ExtensionManager` workload flow can participate without extension author reliance on internal node APIs.
6. Under forced backpressure (tiny buffer), `turn_accepted`, `turn_final`, and `commit_final` are delivered in-order with strictly increasing `seq` and no duplicates.
7. Under forced delta dropping, stream includes `dropped_seq_ranges` compliant with ordering rules.
8. `mono_ts_ms` is non-decreasing within a turn (diagnostic), while ordering remains seq-based.
9. Under forced cold model load, `model_loading` is emitted within 50 ms of model selection.
