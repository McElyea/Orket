# ODR v1 Implementation Plan

Date: 2026-02-26
Status: active
Execution mode: deterministic vertical slices

## Slice ODR-1: Contracts and Parsers
Objective:
Implement strict parser contracts and parse result structures.

Tasks:
1. Add `ParseResult` and parser error-code enums.
2. Implement Architect parser with required ordered headers.
3. Implement Auditor parser with required ordered headers.
4. Enforce duplicate detection and `HEADER_OUT_OF_ORDER`.
5. Add newline normalization helper used by parsers.

Exit Criteria:
1. Parsers never raise; always return `ParseResult`.
2. Header matching and order behavior align with requirements.

## Slice ODR-2: Metrics and Stop Evaluator
Objective:
Implement deterministic lexical metrics and stop evaluator.

Tasks:
1. Implement normalization/tokenization/shingling/Jaccard/diff ratio.
2. Implement stop evaluator with locked priority:
- `CODE_LEAK`
- `MAX_ROUNDS`
- `DIFF_FLOOR`
- `CIRCULARITY`
3. Ensure `MAX_ROUNDS` still records applicable metrics.

Exit Criteria:
1. Stop reason outputs are deterministic and spec-aligned.
2. Metric fields are null only when not applicable.

## Slice ODR-3: Round Runner and Trace
Objective:
Implement `run_round` deterministic state transition and trace emission.

Tasks:
1. Implement no-op behavior when state already stopped.
2. Add code-leak pre-parse safety check over both raw outputs.
3. Implement parse-error handling with `parse_errors` trace field.
4. Emit required trace record schema with `run_config` per record.

Exit Criteria:
1. One record per attempted round.
2. No record appended on post-stop no-op calls.

## Slice ODR-4: Schema and Acceptance Tests
Objective:
Lock condenser artifact schema and pass synthetic acceptance suite.

Tasks:
1. Add `artifact.schema.json` with strict required keys and no extras.
2. Implement canonical fixture-based tests for:
- `CODE_LEAK`
- `DIFF_FLOOR`
- `CIRCULARITY`
- `SHAPE_VIOLATION`
- `MAX_ROUNDS`
- trace completeness
3. Add regression assertions for deterministic parse errors and nullability.

Exit Criteria:
1. `tests/kernel/v1/test_odr_core.py` passes fully.
2. No reliance on network, model adapters, or filesystem writes.

## Validation Commands
1. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
2. `python scripts/check_volatility_boundaries.py`
3. `python -m pytest -q tests/kernel/v1/test_odr_core.py`
4. `python -m pytest -q`
