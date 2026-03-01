# Reforger v0 - Implementation Plan

Date: 2026-02-28  
Status: planned  
Project: `docs/projects/reforger-textmystery-adapter/`

## 0. Scope

Implement v0 in ordered phases with one route (`textmystery_persona_v0`) and one mode (`truth_only`), with deterministic artifact-first behavior.

## 1. Phase 1: Canonical Serialization Utility

Deliverables:

- canonical JSON serializer utility with locked rules:
  - UTF-8 no BOM
  - LF newline
  - sorted keys
  - fixed indent=2
  - finite floats only
- canonical digest utility:
  - `sha256(canonical_json_bytes)`

Exit checks:

- byte-stable canonical JSON for same object
- digest stable across reruns

## 2. Phase 2: Route Metadata Schema

Deliverables:

- route metadata contract with:
  - `route_id`
  - expected inputs
  - `allowed_patch_paths`
  - ordering policies
- `textmystery_persona_v0` route metadata defined in data

Exit checks:

- route metadata validates
- patch-surface checks read metadata, not hardcoded per route

## 3. Phase 3: Inspect Pipeline

Deliverables:

- `reforge inspect` command
- deterministic route selection logic
- route plan + normalize validation diagnostics
- readiness flags:
  - `runnable`
  - `suite_ready`
  - `suite_requirements`
- stable issue-code emission

Exit checks:

- inspect without mode sets `suite_ready: null`
- inspect with `truth_only` evaluates suite readiness only
- deterministic errors for missing/ambiguous routes

## 4. Phase 4: Materializer + Round-Trip

Deliverables:

- deterministic materializer for TextMystery route outputs
- atomic write strategy:
  - temp write + commit/rename
  - no partial outputs on failure
- `reforge materialize` command

Exit checks:

- round-trip idempotence:
  - normalize -> materialize -> normalize digest unchanged
- failure emits `validation_report.materialize.json`

## 5. Phase 5: Scenario Pack Runner

Deliverables:

- strict file-backed scenario pack loader
- schema validation:
  - `pack_id`, `version`, `mode`, non-empty tests
- deterministic scenario report generation

Exit checks:

- mode mismatch fails deterministically
- scenario report includes versioned schema

## 6. Phase 6: Deterministic Patch Loop (Non-Agent)

Deliverables:

- baseline deterministic patch proposer
- candidate evaluation loop with deterministic selection/tie-break
- patch validator enforcing:
  - allowed surface
  - schema validity
  - reference integrity

Exit checks:

- same seed/config => same selected candidate
- out-of-surface patch rejected with `PATCH_OUT_OF_SURFACE`

## 7. Phase 7: Reforger CLI Integration

Deliverables:

- `reforge run` command path for normalize->reforge->materialize
- deterministic run id derivation from locked inputs
- artifact bundle emission on success/failure

Exit checks:

- required artifact files always present
- run id deterministic and timestamp-free

## 8. Phase 8: Operator Wrapper Integration

Deliverables:

- operator wrapper invokes `inspect`
- deterministic plain-language diagnostics rendering
- optional proposal flow for user/operator patch suggestions
- proposal artifacts recorded

Hard boundary:

- operator never applies patches or writes outputs directly

Exit checks:

- operator-proposed patches pass through core validation/apply only

## 9. PR Slice Suggestion

- PR1: canonical serializer + digest + tests
- PR2: route metadata + inspect + issue catalog
- PR3: materializer + atomic writes + round-trip tests
- PR4: scenario pack loader + scenario report
- PR5: deterministic patch loop + selection rules
- PR6: run/artifact bundle hardening + run id
- PR7: operator wrapper integration + proposal artifacting

## 10. Done Definition

v0 is complete when all requirements in `01-REQUIREMENTS.md` section 18 and lock addendum checks are satisfied by passing tests in `03-TEST-MATRIX.md`.
