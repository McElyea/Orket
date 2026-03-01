# Orket Reforger v0 - Requirements

Date: 2026-02-28  
Status: locked-for-implementation  
Owner: Orket Core

## 0. Goal

Build a deterministic reforger that:

- normalizes multiple authoring inputs into a canonical, schema-validated blob
- applies bounded reforge passes under explicit constraints (v0: `truth_only`)
- materializes back into the same authoring formats with stable diffs
- emits artifact-first bundles for replay, CI, and debugging

Integration constraint:

- Orket operator CLI may be used as an interaction front-end
- reforger core remains non-interactive and authoritative

## 1. Problem Statement

Extension authors maintain multiple human-authored files (`YAML`/`JSON`/`TXT`) defining personas, archetypes, and behavior rules. Manual prompt tuning is slow and model-specific.

Required pipeline:

- normalize inputs -> canonical blob
- validate schema + references with machine-readable diagnostics
- reforge via bounded patch proposals + scenario verification
- materialize deterministically
- prove determinism with stable digests and idempotent round-trip

## 2. Non-Goals (v0)

- no GUI requirement (operator CLI is allowed)
- no autonomous agent filesystem writes outside patch interface
- no open-ended reasoning engine outside bounded patch proposals
- no attempt to support every authoring style
- no dependency on any single model as authoritative

## 3. System Architecture Overview

Compiler-style phases:

1. Normalize (front-end): inputs -> canonical blob + diagnostics + digest
2. Reforge (middle-end): propose/evaluate patch sets against constraints + scenario pack
3. Materialize (back-end): canonical blob -> regenerated files + output digests

Authority boundary:

- operator CLI can inspect, explain, collect user choices, and propose patches
- only reforger core validates/applies patches and writes outputs

## 4. Determinism and Artifact Guarantees (Hard)

Given identical:

- canonical blob digest
- reforger config (`mode`, `seed`, `max_iters`, weights)
- scenario pack (`pack_id`, `version`)
- proposer config (including model config if used)

Must produce identical:

- selected patch set
- final canonical digest
- materialized outputs (byte-stable under canonicalization rules)
- score report
- artifact bundle digests

If LLM proposer is used, determinism is required only with fixed recorded config.  
v0 must always support deterministic non-agent proposer.

## 5. Public Interfaces

## 5.1 Reforger CLI (Authoritative, Non-Interactive)

- `reforge inspect <route_id?> --in <dir> [--mode <mode>]`
- `reforge run <route_id> --in <dir> --out <dir> --mode <mode> [--seed N] [--max_iters K]`
- `reforge materialize <route_id> --in-canonical <blob> --out <dir>`

Rules:

- `inspect` emits structured diagnostics + route plan
- `run` always emits artifact bundle, including failures
- `materialize` is deterministic and atomic

## 5.2 Orket Operator CLI Integration (Required, Non-Authority)

Operator CLI may:

- call `reforge inspect`
- explain diagnostics
- collect missing fields/choices
- propose patches

Operator CLI may not:

- bypass core validation
- decide validity
- write final outputs directly

## 6. Route System Contract

Route defines round-trip mapping between known file set and canonical blob.

`inspect` must emit `route_plan.json` with:

- `version`
- selected route/candidates + deterministic rationale
- expected inputs with found/missing status
- parse/schema/reference errors
- missing required fields
- unknown references
- warnings
- deterministic next-step hints (optional)

Route selection order:

1. explicit `route_id`
2. exact filename signature
3. content signature only if unambiguous
4. else deterministic failure `ROUTE_AMBIGUOUS`

## 7. Canonical Blob Contract

Canonical blob is single source of truth.

Requirements:

- JSON-serializable
- schema-validated
- explicit `version`
- stable IDs for referenced entities
- explicit ordering rules or deterministic global sort

Minimal top-level:

- `version`
- `banks`
- `entities`
- `rules`
- `serialization`

## 8. Diagnostics Contract (Core -> Operator)

Machine-readable, stable diagnostics.

Required files:

- `validation_report.normalize.json`
- `validation_report.materialize.json` (when applicable)

Required issue fields:

- `code`
- `severity`
- `path`
- `message`
- optional: `hint`, `expected`, `found`, `suggested_fix`

Full-suite readiness in `inspect`:

- `runnable: bool`
- `suite_ready: null|true|false`
- `suite_requirements[]` exact missing files/fields for mode

## 9. Materialization Contract

Deterministic and idempotent.

Invariant:

- `N = normalize(inputs)`
- `O = materialize(N)`
- `normalize(O)` must equal `N` by canonical digest (ideally byte-identical canonical serialization)

Ordering/canonicalization:

- maps: lexicographic sort unless route override
- lists: explicit per-list ordering policy
- emitted YAML/JSON canonicalized to avoid incidental diffs

Failure semantics:

- materialization is atomic
- invalid canonical blob => no outputs written
- emit `validation_report.materialize.json`
- exit non-zero
- still emit artifact bundle

## 10. Reforge Engine Contract

Patch-only mutation over canonical blob.

Patch format:

- `op: add|remove|replace|move`
- `path: /...`
- `value: ...` (if needed)

RFC6902 is allowed.

All patches must:

- be within allowed patch surface
- preserve schema validity and reference integrity
- be applied only through core

Candidate loop:

1. propose deterministic candidate patch sets
2. apply to blob copy
3. validate schema/references
4. materialize in temp (recommended)
5. run scenario pack and score
6. select best candidate deterministically

## 11. Agent-Assisted Proposer (Optional v0)

Allowed as proposer only.

Input:

- canonical blob
- explicit constraints
- structured scenario failures
- allowed edit surface
- seed/config

Output:

- patch sets only

Safety:

- reject out-of-surface patches
- reject schema/reference-breaking patches
- record full proposal and config artifacts

v0 must work with no agent proposer.

## 12. Scenario Packs and Scoring

Scenario pack fields:

- `pack_id`
- `version`
- deterministic tests (seeded if randomized)
- structured per-test diagnostics
- assertions and metrics

Score report includes:

- overall score
- per-category scores
- baseline delta
- failure reasons with implicated blob paths when available

## 13. Modes (v0)

Required mode: `truth_only`

Constraints:

- never emit lies relative to world facts
- refusal is allowed
- unknown info => refusal or don’t know per mode rules

Verification:

- truth harness detects contradictions
- refusal-variety metric allowed if deterministic

Architecture remains data-driven for future modes.

## 14. Cross-Model Strategy (Policy Hook Only)

Support mechanism for:

- model-agnostic base blob
- optional model overlays via deterministic patch sets

Specific overlay policy is out of scope for v0.

## 15. Required Artifact Bundle (Every Run)

- `inputs_manifest.json`
- `route_plan.json`
- `canonical_blob.json`
- `canonical_digest.txt` or json equivalent
- `candidates.jsonl` or `candidates/`
- `scenario_report.json`
- `outputs_manifest.json` (if outputs produced)
- `final_score_report.json`
- `run_meta.json`

If operator involved:

- `operator_session.json` and/or `operator_proposed_patches.json`

## 16. Required Acceptance Tests

- determinism: same inputs/config => identical outputs and bundle digests
- round-trip idempotence: normalize->materialize->normalize digest unchanged
- schema/reference integrity: deterministic failure with stable issue codes
- mode verification: truth_only baseline passes; reforging does not regress truth constraints
- patch safety: out-of-surface and schema-breaking patches rejected
- operator integration: operator can render inspect gaps; core still validates/applies patches

## 17. Implementation Sequencing (Reference)

1. route system + inspect pipeline
2. canonical schema + deterministic serialization + digest
3. materializer + round-trip tests
4. scenario runner + scoring report
5. deterministic non-agent patch loop
6. optional agent proposer via patch interface
7. operator wrapper flow (inspect/explain/propose only)

## 18. v0 Exit Criteria

v0 complete when:

- `reforge inspect` works for at least one route with actionable diagnostics
- `reforge run` performs normalize->reforge->materialize for at least one route
- artifact bundle emitted every run
- round-trip idempotence validated
- `truth_only` scenario pack integrated and baseline passing
- patch interface stable
- operator CLI can run inspect, explain suite gaps, and forward proposals through core validation

## 19. Lock Addendum (Frozen Decisions)

### 19.1 Canonical Serialization (Hard Lock)

- UTF-8 without BOM
- LF only
- JSON only internally
- lexicographic key ordering
- no trailing whitespace
- fixed indentation: 2 spaces
- disallow NaN/Infinity
- JSON default float repr (no extra trailing-zero normalization)
- stable object normalization before hashing

Canonical digest:

- `sha256(bytes_of_canonical_json_string)`
- byte hash of canonical JSON string only
- do not mix semantic/object hashing

### 19.2 Deterministic Tie-Break Rules (Single Source)

Candidate selection order:

1. fewer hard violations
2. higher overall score
3. fewer soft fails
4. deterministic scenario metric tie-break (if configured)
5. candidate id lexicographic ascending

Candidate id format:

- `candidate_<zero_padded_index>`
- no UUID/time ids

### 19.3 Stable Issue Code Catalog (v0)

Frozen codes:

- `ROUTE_AMBIGUOUS`
- `ROUTE_NOT_FOUND`
- `INPUT_MISSING`
- `PARSE_ERROR`
- `SCHEMA_INVALID`
- `REF_INVALID`
- `MISSING_REQUIRED_FIELD`
- `PATCH_OUT_OF_SURFACE`
- `PATCH_SCHEMA_BREAK`
- `PATCH_REF_BREAK`
- `MODE_UNSUPPORTED`
- `SUITE_NOT_READY`
- `INTERNAL_ERROR`

### 19.4 Inspect Behavior Clarification

- `inspect` without `--mode`:
  - route + normalize validation only
  - `suite_ready: null`
- `inspect --mode truth_only`:
  - normalize validation + suite readiness check only
  - `suite_ready: true|false`
- no scenario scoring in inspect

### 19.5 Materialize Failure Semantics (Frozen)

- atomic writes only
- invalid canonical -> no partial outputs
- emit `validation_report.materialize.json`
- non-zero exit
- artifact bundle still emitted

### 19.6 Artifact Schema Versioning (Hard Lock)

- `run_meta.version = "reforger_v0"`
- `route_plan.version = "route_plan_v0"`
- `validation_report.version = "validation_v0"`
- `scenario_report.version = "scenario_v0"`

Schema changes require version increment.

### 19.7 Allowed Patch Surface (Data-Driven)

Each route defines `allowed_patch_paths`, e.g.:

```json
{
  "route_id": "textmystery_persona_v0",
  "allowed_patch_paths": [
    "/banks",
    "/rules",
    "/entities/*/prompt_overrides"
  ]
}
```

Core validator must enforce route metadata policy.  
No hardcoded path policy in general logic.

### 19.8 Canonical Digest Rule (Final)

- digest is `sha256(canonical_json_bytes)`
- never hash parsed object, pretty variant, or YAML

### 19.9 Deterministic Run ID

Derived from hash of:

- canonical digest
- mode
- seed
- max_iters
- scenario pack version
- proposer config

Stored as hex prefix (example: first 16 chars).  
No timestamps in run id.

### 19.10 Test Matrix Tightening

Must explicitly assert:

- canonical JSON byte identity across runs
- artifact digest identity across runs
- tie-break reproducibility
- exact issue codes
- patch-surface enforcement via route metadata
- atomic materialization behavior
