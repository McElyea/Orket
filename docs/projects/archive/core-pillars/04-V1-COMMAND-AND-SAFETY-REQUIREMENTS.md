# Core Pillars v1 Command and Safety Requirements

Date: 2026-02-24  
Status: active  
Source: extracted from `docs/projects/ideas/Ideas.md` (chatter removed)

## Objective
Define command-level contracts and safety physics for v1 so Orket is predictable, local-first, and fail-closed on repository mutations.

## Scope
Applies to v1 command surface:
1. `orket init`
2. `orket api add`
3. `orket refactor`
4. `orket swap`

## System Requirements
1. Local execution and privacy:
- baseline workflows must run without internet dependency
- no telemetry by default
- network integrations must be explicit opt-in

2. Guardrails and transaction safety loop:
- every mutating command must run:
  - plan (touch-set + scope preview)
  - confirmation (unless `--yes`)
  - snapshot
  - execute
  - verify
  - finalize or revert
- if verify fails, repository state must return to pre-run state

3. Scoped writes:
- writes allowed only inside user scope and computed touch set
- attempts outside allowed paths must hard-fail with policy error

4. VRAM-aware operation:
- task-specific model load/unload lifecycle
- manual model swap supported
- one-task-at-a-time model budget behavior for single GPU setups

## Command Contracts
1. `orket init`:
- hydrates local blueprint/templates, not freeform full-project hallucination
- produces compile/lint-ready baseline and project run instructions
- verification gates run by default unless disabled

2. `orket api add`:
- generates route/controller/types using existing project style
- modifies only planned files in allowed scope
- on verification failure, must fail-closed and surface draft diagnostics

3. `orket refactor`:
- must support dry-run touch-set planning
- must enforce write barrier during patch application
- must snapshot before write and auto-revert on verify failure

4. `orket swap`:
- explicit manual model priority and lifecycle command
- must not mutate project files

## Error Contract (v1 Baseline)
Use stable machine-readable error codes for safety workflow:
1. `E_SCOPE_REQUIRED`
2. `E_TOUCHSET_EMPTY`
3. `E_WRITE_OUT_OF_SCOPE`
4. `E_MODEL_OUTPUT_OUT_OF_SCOPE`
5. `E_VERIFY_FAILED_REVERTED`
6. `E_CONFIG_INVALID`
7. `E_GIT_REQUIRED`
8. `E_UNSUPPORTED_INSTRUCTION`
9. `E_INTERNAL`

## Non-Goals (v1)
1. Cryptographic attestation and signed receipts.
2. Cross-machine bit-identical reproducibility guarantees.
3. Hermetic proxy infrastructure.
4. OS-first distributed control-plane scope.
5. Replay as a global cross-feature policy engine.

## Acceptance Gates
1. A1 Safety:
- failed mutation leaves repo bit-identical to pre-run state

2. A2 Barrier:
- out-of-scope writes fail with barrier error

3. A3 Advisory memory integration:
- previous failure warnings are displayed in planning phase when relevant

4. A4 Deterministic rollback path:
- verify failure always triggers deterministic revert semantics
