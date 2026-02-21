# Skills Implementation Plan

Last updated: 2026-02-21
Owner: Orket Core
Status: Draft (active refinement)

## Scope
This document defines the implementation plan for the Orket Skill Contract and Skill loader/runtime path in the Local Skill Runtime (LSR).

Primary goals:
1. Make Skill loadability contract-first and mechanically enforceable.
2. Add deterministic validation outputs for Skill eligibility and risk.
3. Enforce schema, fingerprint, permission, and runtime pinning guarantees at load time.
4. Integrate Skill entrypoints with tool profile linkage for runtime usage.

Non-goals (v1):
1. Skill marketplace/distribution workflows.
2. Remote execution orchestration.
3. Cross-cluster trust and signing infrastructure beyond local contract checks.

## Contract Baseline
Source baseline: `Agents/Ideas.md` (ORKET SKILL CONTRACT, v`1.0.5` draft).

Implementation target includes:
1. K0-K21 contract clauses.
2. Loader outcomes with canonical error codes.
3. I1-I4 invariants as hard checks.

## Architecture Delta (Target)
1. New Skill contract models:
`orket/core/contracts/skills/`
2. New Skill validation service:
`orket/application/services/skills/`
3. New loader policy checks:
`orket/application/services/skills/skill_loader.py`
4. Validation/loader artifacts and diagnostics:
`workspace/.../observability/.../skill_validation.json`
5. Skill schema docs and references:
`docs/specs/` and `docs/archive/` where applicable.

## Phase Plan

### Phase 0: Contract Freeze
Deliverables:
1. Canonical Skill manifest schema (`skill_contract_version` aware).
2. Entrypoint execution-context schema.
3. Permission and side-effect category schema (core + namespaced extension rules).
4. Loader error payload schema + canonical error codes.
5. Determinism eligibility output schema.

Exit criteria:
1. Schemas are checked in and versioned.
2. Fixture examples include valid + intentionally invalid manifests.
3. Contract tests fail on missing required fields/invariants.

### Phase 1: Validation Engine
Deliverables:
1. Schema validation for identity/entrypoint/input/output/error/fingerprint fields.
2. Validation metadata generation (`contract_valid`, `determinism_eligible`, risk fields).
3. Runtime pinning checks for python/node/container/shell.
4. Side-effect declaration and fingerprint coverage checks.

Exit criteria:
1. Validator emits deterministic output for identical input manifests.
2. Invalid references and undeclared behavior are surfaced with canonical error codes.

### Phase 2: Loader Enforcement
Deliverables:
1. Loader rejects non-compliant Skills by default.
2. Structured rejection payload with `validation_stage`, `entrypoint_id`, and retryability flags.
3. Unsupported contract-version behavior (`ERR_CONTRACT_UNSUPPORTED_VERSION`).

Exit criteria:
1. No invalid skill manifests are loadable.
2. Rejection payloads match the loader error schema.

### Phase 3: Tool Adapter Integration
Deliverables:
1. Entry-point to tool mapping via `tool_profile_id` + `tool_profile_version`.
2. Determinism-eligibility aware adapter behavior.
3. Runtime limits enforcement wiring (`max_execution_time`, `max_memory`, optional cpu/disk).

Exit criteria:
1. Loaded Skills can be invoked only via declared entrypoints.
2. Adapter rejects undeclared entrypoints and invalid permission usage.

### Phase 4: Hardening and Rollout
Deliverables:
1. Contract tests and integration tests across Skill validation + loader + adapter paths.
2. CI gate coverage for Skill contract conformance.
3. Runbook updates for debugging loader/validation failures.

Exit criteria:
1. Green deterministic contract checks in CI.
2. Clear operator diagnostics for each canonical loader error.

## Remaining Backlog
1. Add Skill adapter/runtime mapping for `entrypoint_id -> tool_profile_id/tool_profile_version`.
2. Add adapter enforcement tests for undeclared entrypoint invocation rejection.
3. Add adapter enforcement tests for undeclared permission usage rejection.
4. Wire `scripts/check_skill_contracts.py` into the quality lane after adapter enforcement lands.

## Definition of Done (v1)
1. Skill loadability is contract-first and enforced mechanically.
2. Loader error output is canonical and machine-readable.
3. Determinism eligibility metadata is stable and reproducible.
4. Skill entrypoints integrate with tool profiles without undeclared behavior leaks.
