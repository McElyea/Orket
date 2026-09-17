# Shared immutable run admission

## Summary
- Owner: Orket Core
- Date: 2026-09-14
- Contract: `docs/specs/CONTROL_PLANE_TERMINAL_AUTHORITY.md` and the existing
  `ControlPlaneExecutionRepository.save_run_record` port.
- Status: scoped source, installed and native acceptance passes; broader BT-5 remains open.

## Delta
- The old shared repository replaced the entire run payload on ID conflict.
  Installed controls after healthy composed admission replace namespace in each
  outward/cards/governed-agent family. Identical controls pass; three required
  refusals fail. Retained evidence: `.tmp/bt5-cards-admission/authority-mutation.json`.
- The shared core rule now treats only lifecycle state, current attempt and
  final-truth references as mutable state. All other admission fields are compared
  before writing, under one SQLite writer transaction. Conflict preserves retained
  authority; same admission and state-only updates remain supported. The writer
  captures and validates incoming JSON before its first await, then compares,
  persists and returns that same snapshot. Invalid contract versions remain
  schema errors, distinct from conflicting valid admission.
- Governed-agent reentry uses the same comparison while retaining original
  creation time. Kernel reentry refuses missing scope instead of silent backfill.
- This implements the BT-5 immutable admission predicate. It does not supply
  general state CAS, effect fencing, lifecycle transitions or terminal proof.

## Migration Plan
1. Stop older writers; mixed permissive/new writers are unadmitted.
2. Preserve historical records and original evidence. Normal reentry cannot
   backfill namespace or overwrite a changed admission to repair inconsistency.
3. Prove all immutable fields through standalone and borrowed transaction ports,
   native competing writers, composed families, existing recovery/terminal
   regressions, installed packages and actual llama.cpp success/unsuccessful CLI.
   The accepted evidence is `.tmp/bt5-run-immutability/gate-verified/audit.json`:
   1,120 cases pass in source and each Windows/Linux Python 3.11/3.12 installed
   cell, with exact artifact/origin checks and retained native/API evidence.

## Rollback Plan
1. Stop affected admission on inconsistent history or transaction failure.
2. Retain databases, snapshots, ledgers and effects; repair forward. Do not restore
   permissive overwrite or silently invent missing scope.
3. Explicit historical repair remains separately admitted work.

## Versioning Decision
- Patch-level behavioral repair in the uncommitted 0.6.2 candidate.
- No schema or successful response change; changed admission now raises the
  existing repository conflict type with `E_CONTROL_PLANE_RUN_AUTHORITY_CONFLICT`.
- No release, tag or push is performed here.
