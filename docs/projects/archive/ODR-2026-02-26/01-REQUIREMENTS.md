# ODR v1 Requirements

Date: 2026-02-26
Status: active

## Objective
Implement Orket Distillation Reactor (ODR) v1 as a deterministic steel-thread loop for Architect/Auditor outputs with strict shape validation, stop logic, and machine-readable in-memory trace.

## Non-Goals
1. Real LLM invocation.
2. Retry orchestration.
3. Filesystem writes.
4. Condenser execution (schema only in v1).
5. Embedding or semantic similarity methods.

## Deliverables
1. `docs/odr/requirements.md`
2. `docs/odr/prompts.md`
3. `docs/odr/stoplogic.md`
4. `orket/kernel/v1/odr/__init__.py`
5. `orket/kernel/v1/odr/core.py`
6. `orket/kernel/v1/odr/parsers.py`
7. `orket/kernel/v1/odr/metrics.py`
8. `orket/kernel/v1/odr/artifact.schema.json`
9. `tests/kernel/v1/test_odr_core.py`

## Locked State Machine Order
1. Ingest raw outputs.
2. `CODE_LEAK` check (architect + auditor raw).
3. Parse/validate (`SHAPE_VIOLATION` on parse failure).
4. Append `Vn` to `history_v`.
5. Evaluate `MAX_ROUNDS` when `n == max_rounds`.
6. Evaluate `DIFF_FLOOR`.
7. Evaluate `CIRCULARITY`.
8. Apply stop precedence for metric phase: `MAX_ROUNDS > DIFF_FLOOR > CIRCULARITY`.
9. Emit trace record.

## Parsing Contract
1. Headers are case-insensitive and whitespace-tolerant.
2. Headers must include `###` prefix and exact required header text.
3. Architect required order:
- `REQUIREMENT`
- `CHANGELOG`
- `ASSUMPTIONS`
- `OPEN_QUESTIONS`
4. Auditor required order:
- `CRITIQUE`
- `PATCHES`
- `EDGE_CASES`
- `TEST_GAPS`
5. Duplicate required headers are invalid.
6. Parsers must return `ParseResult` and must not raise exceptions.
7. Allowed parse error codes:
- `EMPTY_INPUT`
- `MISSING_HEADER`
- `DUPLICATE_HEADER`
- `HEADER_OUT_OF_ORDER`
- `EMPTY_REQUIREMENT`

## Config Contract (Defaults)
1. `max_rounds=8`
2. `diff_floor_pct=0.05`
3. `stable_rounds=2`
4. `shingle_k=3`
5. `margin=0.02`
6. `min_loop_sim=0.65`
7. `code_leak_patterns`:
- `(?s)```.*?````
- `\\b(def|class|import|fn|let|const|interface|type)\\b`
- `\\b(npm|pip|cargo|docker|venv|node_modules)\\b`

## Trace Contract
1. One strict trace record per attempted round.
2. `run_config` included in every record.
3. `parse_errors` included in every record:
- `[]` on success
- one entry per failing parser on `SHAPE_VIOLATION`
4. For `CODE_LEAK` and `SHAPE_VIOLATION`:
- `architect_parsed = null`
- `auditor_parsed = null`
5. Metrics nullability must be deterministic (`null` when not applicable).

## Determinism Rules
1. Normalize newlines (`\r\n` and `\r` to `\n`) before regex checks and parsing.
2. Diff floor comparison uses strict `<`.
3. Circularity margin comparison uses strict `>`.
4. `run_round` after stop (`state.stop_reason != null`) is a no-op and appends no new trace.

## Acceptance Tests
1. `CODE_LEAK` triggers and parsed fields are null.
2. `DIFF_FLOOR` triggers under locked fixtures.
3. `CIRCULARITY` triggers under locked fixtures.
4. `SHAPE_VIOLATION` triggers with missing/invalid headers and trace contains parse errors.
5. `MAX_ROUNDS` triggers when `n == max_rounds`.
6. Trace completeness and nullability invariants hold.
