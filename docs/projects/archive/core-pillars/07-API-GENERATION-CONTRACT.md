# Core Pillars API Generation Contract (v1)

Date: 2026-02-24  
Status: active

## Objective
Define a deterministic, safe contract for `orket api add` so generated API surfaces are reproducible, idempotent, and easy for humans to extend.

## Scope
Applies to `orket api add` in CP-1.

## Inputs
1. route name
2. method
3. schema fields
4. auth mode (optional)
5. scope and project style target

## Deterministic Output Contract
1. Generated files and edits must be deterministic for the same inputs and repo state.
2. File naming and symbol naming must follow one canonical naming policy per framework adapter.
3. Generated route artifacts must include:
- route definition
- handler/controller stub
- request/response type definitions
- deterministic test template file(s)

## Idempotency Contract
1. Re-running the same `orket api add` command must not duplicate route registration.
2. Re-running must not duplicate type declarations or test files.
3. If route already exists:
- command returns explicit idempotent outcome
- no-op mutation is recorded in command output

## Extension-Point Contract
1. Generated files must include explicit human-edit extension regions.
2. Extension regions must be preserved across future generation passes.
3. Generator-owned regions and user-owned regions must be clearly separated by markers.

## Safety and Verification Contract
1. All writes constrained by command scope and touch set.
2. Mutations executed under transaction loop:
- plan -> snapshot -> execute -> verify -> finalize/revert
3. Verification minimum:
- typecheck
- lint
4. On verification failure:
- revert all mutations
- emit draft-failure diagnostics
- preserve deterministic failure code behavior

## Framework Support Contract (v1)
1. Support only explicitly declared framework adapters in v1.
2. Unsupported framework must fail with explicit `unsupported style` error.
3. No best-effort silent style inference fallback.

## Test Generation Contract (v1)
1. Test output is template-driven, not model-invented structure.
2. Route tests must validate:
- route registration
- request shape handling
- response status/body baseline
3. Template test packs are versioned and adapter-specific.

## Acceptance Tests
1. API-1 deterministic output:
- same input produces same generated content

2. API-2 idempotent rerun:
- second run is no-op and non-duplicating

3. API-3 extension preservation:
- user edits inside extension region survive rerun

4. API-4 fail-closed verification:
- failed verify fully reverts repo state

5. API-5 scope barrier:
- out-of-scope mutation attempts fail deterministically
