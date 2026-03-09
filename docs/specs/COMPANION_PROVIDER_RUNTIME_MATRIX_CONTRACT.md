# Companion Provider Runtime Matrix Contract

Last updated: 2026-03-09
Status: Active
Owner: Orket Core

## 1. Purpose

This document defines the canonical output and behavior contract for:

1. `scripts/companion/run_companion_provider_runtime_matrix.py`
2. `scripts/companion/render_companion_provider_runtime_report.py`

The matrix artifact is used to evaluate Companion runtime behavior across provider/model combinations and produce rig-class recommendations with explicit blocker reporting.

## 2. Canonical Paths

Canonical JSON output path:

1. `benchmarks/results/companion/provider_runtime_matrix/companion_provider_runtime_matrix.json`

Canonical markdown report output path:

1. `benchmarks/results/companion/provider_runtime_matrix/README.md`

Canonical schema path:

1. `docs/specs/companion-provider-runtime-matrix.schema.json`

The JSON file is rerunnable and must preserve `diff_ledger` append behavior through `write_payload_with_diff_ledger`.

## 3. Invocation Contract

Base command:

1. `python -m scripts.companion.run_companion_provider_runtime_matrix`

Validation command:

1. `python -m scripts.companion.validate_companion_provider_runtime_matrix`

Pipeline command (generate + validate + render):

1. `python -m scripts.companion.run_companion_provider_runtime_matrix_pipeline`

Key options:

1. `--providers` comma list (default `ollama,lmstudio`)
2. `--models` comma list
3. `--provider-model-map` explicit map format:
   1. `provider=model1|model2;provider2=model3`
4. `--rig-classes` comma list from `A,B,C,D`
5. `--usage-profiles` comma list from `chat-first,memory-heavy,voice-heavy`
6. `--stability-attempts` integer >= 1
7. `--output` artifact output path

Case selection rules:

1. If `--provider-model-map` is provided and valid, it is authoritative.
2. Else if one provider and multiple models are provided, run one case per model.
3. Else fallback to provider/model zip semantics.

## 4. Top-Level Payload Schema

Required top-level keys:

1. `generated_at_utc`: ISO-8601 UTC timestamp
2. `status`: `complete | partial`
3. `observed_result`: `success | partial success | failure`
4. `providers_requested`: list[str]
5. `models_requested`: list[str]
6. `case_pairs_requested`: list[object]
7. `rig_classes_requested`: list[str]
8. `usage_profiles_requested`: list[str]
9. `cases`: list[object]
10. `recommendations`: object
11. `blockers`: list[object]
12. `summary`: object
13. `diff_ledger`: list[object] (added/updated by diff-ledger writer)

## 5. Case Schema

Each item in `cases` must include:

1. `provider`: str
2. `model`: str
3. `observed_path`: `primary | degraded | blocked`
4. `result`: `success | failure`
5. `scores`: object containing all dimensions:
   1. `reasoning`
   2. `conversational_quality`
   3. `memory_usefulness`
   4. `latency`
   5. `footprint`
   6. `voice_suitability`
   7. `stability`
   8. `mode_adherence`

Success case fields:

1. `latency_ms` average chat latency for measured prompts
2. `message_preview` short preview string
3. `stt_available` bool

Failure case fields:

1. `failed_step` explicit failing step
2. `error` explicit failure error

## 6. Score Entry Schema

Each score entry is an object:

1. `status`: `measured | not_measured`
2. `value`: float in `[0.0, 1.0]` when measured, else `null`
3. `detail` optional detail string

Coverage rule:

1. A successful case with one or more `not_measured` score dimensions must emit a coverage blocker entry.

## 7. Recommendations Schema

`recommendations` contains:

1. `usage_profiles`: list[str]
2. `rig_classes`: list[str]
3. `by_rig_class`: object keyed by rig class
4. `candidate_scores`: list[object]

`by_rig_class[<class>][<profile>]` entry must be:

1. recommended row:
   1. `status`: `recommended`
   2. `provider`: str
   3. `model`: str
   4. `composite_score`: float
   5. `profile_score`: float
   6. `profile_coverage`: float
   7. `rig_fit_score`: float
   8. `missing_dimensions`: list[str]
2. or blocked row:
   1. `status`: `blocked`
   2. `reason`: str

## 8. Blocker Schema

Each blocker row contains:

1. `provider`: str
2. `model`: str
3. `step`: str
4. `observed_path`: `degraded | blocked`
5. `category`: `runtime | coverage`
6. `error`: str

Blockers must include exact failing step context whenever available.

## 9. Summary Schema

`summary` contains:

1. `requested_cases`: int
2. `successful_cases`: int
3. `failed_cases`: int
4. `blocker_count`: int

## 10. Status and Exit Semantics

Status rule:

1. `complete` only when:
   1. no failed cases
   2. no blockers
2. otherwise `partial`

Observed-result rule:

1. `success` when status is `complete`
2. `partial success` when status is `partial` and at least one case succeeded
3. `failure` when no case succeeded

CLI exit code rule:

1. exit `0` when `status=complete`
2. exit `2` when `status=partial`

## 11. Markdown Report Contract

`scripts/companion/render_companion_provider_runtime_report.py` consumes matrix JSON and produces markdown with sections:

1. Summary metadata
2. Recommendations table
3. Blockers table
4. Case scores table

The renderer does not mutate the source JSON artifact.

## 12. Verification Expectations

Minimum verification for matrix runner changes:

1. unit/contract tests for selection and scoring behavior
2. integration tests for success/degraded/blocked paths
3. live non-mocked command attempt against local host seam, with explicit blocker capture when unavailable

Minimum verification for report renderer changes:

1. contract test for required sections and key field rendering
2. integration test for CLI write path
