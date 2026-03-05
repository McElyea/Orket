# Protocol Replay Campaign Output Schema (v1)

Last updated: 2026-03-04  
Status: Draft  
Owner: Orket Core

This document freezes the output contract for protocol replay campaign comparisons.

Reference implementation surfaces:
1. `orket/runtime/protocol_determinism_campaign.py`
2. `scripts/protocol/run_protocol_determinism_campaign.py`
3. CLI command: `orket protocol campaign`
4. API endpoint: `/v1/protocol/replay/campaign`

## Purpose

Provide a stable machine-readable payload that operators and CI tooling can use to:
1. Compare deterministic replay state across multiple protocol runs.
2. Detect mismatch regressions before strict enforcement.
3. Capture campaign artifacts for rollback readiness and audit trails.

## Top-Level Shape

```json
{
  "runs_root": "string",
  "baseline_run_id": "string",
  "candidate_count": 0,
  "mismatch_count": 0,
  "all_match": true,
  "comparisons": []
}
```

Field rules:
1. `runs_root`: absolute or resolved path string.
2. `baseline_run_id`: run id used as comparison anchor.
3. `candidate_count`: number of candidate run ids evaluated.
4. `mismatch_count`: number of candidates that did not match baseline.
5. `all_match`: `true` only when `mismatch_count == 0`.
6. `comparisons`: ordered list of per-run comparison rows.

## Comparison Row Shape

Rows come in two forms.

### Missing events row

```json
{
  "run_id": "run-x",
  "status": "missing_events",
  "events_path": "/abs/path/runs/run-x/events.log"
}
```

### Evaluated row

```json
{
  "run_id": "run-a",
  "status": "ok",
  "deterministic_match": true,
  "difference_count": 0,
  "state_digest_a": "sha256 hex",
  "state_digest_b": "sha256 hex",
  "differences": []
}
```

Field rules:
1. `run_id`: candidate run id.
2. `status`: one of:
   - `ok`
   - `missing_events`
3. `deterministic_match`: present only when `status == "ok"`.
4. `difference_count`: length of `differences` when `status == "ok"`.
5. `state_digest_a`: baseline state digest when `status == "ok"`.
6. `state_digest_b`: candidate state digest when `status == "ok"`.
7. `differences`: deterministic diff rows from replay comparator.

## Difference Row Shape

Inherited from replay comparator output:

```json
{
  "field": "status",
  "a": "incomplete",
  "b": "failed"
}
```

Known `field` values:
1. `status`
2. `failure_class`
3. `failure_reason`
4. `last_event_seq`
5. `operations`
6. `artifact_inventory`
7. `receipt_inventory`

## Determinism Contract

For a fixed campaign invocation (`runs_root`, `baseline_run_id`, `run_id` filter):
1. Candidate ordering is lexicographic.
2. Comparison row ordering is deterministic.
3. `difference_count` equals `len(differences)` exactly.
4. `all_match` is derived mechanically from `mismatch_count`.

## Exit-Code Contract

For script and CLI strict mode:
1. `--strict` exits non-zero when `all_match == false`.
2. Non-strict mode always exits zero unless invocation fails before campaign output is produced.

## Validation Guidance

Operator validation checks:
1. `candidate_count` equals expected run set size.
2. `mismatch_count` aligns with number of rows where:
   - `status == "missing_events"` OR
   - `deterministic_match == false`
3. For each mismatched row, `difference_count > 0` unless `status == "missing_events"`.

## Compatibility Policy

1. New optional fields may be added.
2. Existing fields must not change type.
3. Existing enum values must remain valid.
4. Removal or type changes require a schema version bump and migration notes.
