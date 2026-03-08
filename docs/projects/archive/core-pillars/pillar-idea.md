# Core Pillars Idea (Cleaned)

Date: 2026-02-24  
Source: distilled from retired `docs/projects/ideas/Ideas.md`

## Product Thesis
Orket v1 is a predictable local AI dev engine, not an OS-first platform.

Primary user value:
1. Psychological safety when using AI on real code.
2. Fast local workflows on strong desktop hardware.
3. Control, privacy, and deterministic guardrails over raw model intelligence.

## Target Users
1. Power-user engineers.
2. Solo builders.
3. Small technical teams.
4. Users prioritizing local execution and no subscription lock-in.

## Determinism Levels
1. Level 0: Vibe tool (no guarantees) - rejected.
2. Level 1: Session predictability (same input/repo/model/command gives stable results) - v1 target.
3. Level 2: Ledgered reproducibility (heavy replay/audit guarantees) - post-v1 optional.

## No-BS v1 Pillars
1. Scaffolding engine:
- template hydration over freeform generation
- production-ready project baseline from local blueprints

2. API generation:
- typed route/controller/type generation
- project-style-aware connector wiring

3. Guarded refactoring:
- scope-constrained write barrier
- dry-run touch-set preview
- snapshot -> execute -> verify -> finalize/revert safety loop

4. Deterministic test and verification gates:
- local lint/typecheck/test gates on mutating commands
- fail-closed behavior with explicit diagnostics

5. Runtime replay parity (practical):
- deterministic drift detection for command/runtime outputs
- focus on operational parity, not heavy cryptographic replay in v1

6. Local-first privacy:
- no required cloud calls
- no telemetry by default
- explicit opt-in network integrations only

7. VRAM-aware model lifecycle:
- load task model, unload after completion
- manual swap support for constrained single-GPU environments

8. Stateful memory and agents (expansion layer):
- vector memory as durable context substrate
- persistent utility agents after trust layer is stable

## v1 Command Surface
1. `orket init`:
- blueprint hydration with local templates
- produces compile/lint-ready baseline

2. `orket api add`:
- adds typed API route and integration glue
- draft-fail behavior on verification failure

3. `orket refactor`:
- scoped surgical transformations with write barrier
- auto-revert when verification fails

4. `orket swap`:
- manual model priority control for VRAM management

## Required v1 Safety Contracts
1. Every mutating command supports dry-run planning.
2. Every mutating command enforces scoped writes.
3. Every mutating command runs environment verification before finalizing.
4. Verification failure must leave repo exactly at pre-run state.

## Deferred from v1
1. Cryptographic ledgers and signed receipts.
2. Bit-for-bit reproducibility across machines and long timelines.
3. Hermetic proxy architecture.
4. OS-first distributed control-plane expansion.

## Success Criteria
1. Users can run `init`, `api add`, and `refactor` daily without repo trust anxiety.
2. Commands are predictable and locally verifiable.
3. Tool remains useful on local GPU hardware without cloud dependency.
