# Runtime store authority binding

## Summary
- Change title: Freeze runtime storage and migrate legacy relative bindings.
- Owner: Orket Core, architectural-truth BT-5.
- Date: 2026-09-13.
- Affected contract: `docs/specs/RUNTIME_STORE_BINDING.md`.

## Delta
- Current behavior: SQLite follows process CWD for relative paths; control-plane
  composition follows the execution workspace. A paused approval can lose its
  runtime store after a CWD change, and another workspace sees a different target.
- Proposed behavior: resolve the runtime path once and use its sibling
  control-plane store consistently. Explicit offline migration preserves old
  requests and supplies checked per-session storage provenance for their resume.
- Why required now: real card/approval counterexamples in BT-5 contradict a
  single workload authority. A filename-only repair would hide legacy history.

## Migration Plan
1. Compatibility window: no implicit workspace-relative fallback or dual dispatch.
2. Migration steps: follow `RUNTIME_STORE_BINDING.md`; refuse unbound legacy
   relative scopes and conflicting histories before mutation or execution.
3. Validation gates: real pause/approval, copied/WAL history, interruption,
   conflicting-target refusal, restart, installed controls and llama.cpp proof.

## Rollback Plan
1. Trigger: storage redirection, lost retained identity or unauthorized redispatch.
2. Steps: stop admission, preserve both stores and migration records, inspect the
   retained binding before selecting any prior executable.
3. Data/state recovery: no automatic reverse migration, merge or deletion. Old
   executables do not understand the new binding and must remain stopped.

## Versioning Decision
- Version bump type: patch candidate subject to contributor commit/tag policy.
- Effective date: acceptance follows completed migration proof in the canonical plan.
- Downstream impact: relative storage now has a frozen owner; old split histories
  require explicit offline migration. No release is performed by this change.
