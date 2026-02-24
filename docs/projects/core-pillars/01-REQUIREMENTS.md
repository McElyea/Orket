# Core Pillars Requirements

Date: 2026-02-24  
Status: active

## Objective
Ship a practical, modular product direction focused on code generation, correctness, replayability, and sovereign local operation.

Detailed command-level and memory requirements:
1. `docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`
2. `docs/projects/core-pillars/05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`
3. `docs/projects/core-pillars/07-API-GENERATION-CONTRACT.md`

## Product Layers
1. Build Layer:
- Application Scaffolding
- API Generation
- Verified Refactoring

2. Trust Layer:
- Deterministic Test Suites
- Runtime Model Replays

3. State Layer:
- Integrated Vector Memory
- Persistent Personality Bots
- Local Sovereignty (cross-cutting requirement)

## Functional Requirements

1. Application Scaffolding
- Single command scaffolds a production-ready baseline.
- Includes frontend, backend, test layout, and standardized structure.
- Generates manifest/config artifacts compatible with Orket module contracts.

2. API Generation
- Generate route/controller/service scaffolding from declared contracts.
- Emit deterministic API artifact manifest with explicit idempotency behavior.
- Preserve extension points for hand-written business logic.
- Use template test packs for route tests in v1 (no general model-generated test synthesis).

3. Deterministic Test Suites
- Generate stable, replayable tests for scaffolded/generated code.
- Detect model drift through deterministic replay checks and explicit gate failures.
- Include minimal smoke, contract, and regression suites by default.

4. Verified Refactoring
- Support controlled, contract-aware transformations with pre/post parity checks.
- Produce replay evidence and diff artifacts before acceptance.
- Provide rollback-ready output when verification fails.
- Enforce transaction loop: plan -> snapshot -> execute -> verify -> finalize/revert.
- Enforce write barrier and out-of-scope hard failure behavior.

5. Runtime Model Replays
- Persist run metadata and replay payloads with deterministic comparison outputs.
- Enforce schema for replay records and decision traceability.
- Support pre-merge and CI replay checks.

6. Local Sovereignty (Offline Mode)
- Core workflows run without network dependency.
- Offline mode has explicit capability matrix and degraded-mode behavior.
- No hard requirement on external hosted model services for baseline flows.

7. Persistent Personality Bots
- Support persistent, grounded role agents with durable state.
- Scope as utility/task agents; no emotional companion claims.
- Enforce memory safety and role-boundary constraints.

8. Integrated Vector Memory
- Maintain durable retrieval interface with deterministic query behavior.
- Integrate memory with replay/governance artifacts.
- Support module-level ownership boundaries.
- Include Bucket D failure-lesson memory as advisory-only retrieval.

## Non-Functional Requirements
1. All pillar capabilities must be modularized behind engine-first contracts.
2. No new dependency-direction violations.
3. New features require deterministic tests and report artifacts.
4. CI quality workflow runs all required pillar gates in quick/full jobs where applicable.
5. Failure-memory behavior remains advisory and cannot bypass transaction safety rules.

## Acceptance Criteria
1. At least one end-to-end vertical slice for Build Layer is runnable via one CLI command.
2. Deterministic replay detects intentional drift and passes stable baselines.
3. Offline mode baseline matrix is documented and enforced by tests.
4. Generated artifacts and replay outputs are retained under policy controls.
5. Refactor/API mutation commands demonstrate deterministic revert on verify failure.
6. Bucket D lessons are recorded/retrieved with D1-D4 acceptance behavior.
