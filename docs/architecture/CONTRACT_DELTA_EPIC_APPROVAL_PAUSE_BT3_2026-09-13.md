# Epic approval pause and continuation — BT-3

## Summary

- Change title: retain unfinished epic approval execution.
- Owner: Orket Core
- Date: 2026-09-13
- Affected contracts: CARD_COMPLETION_ACCEPTANCE_CONTRACT.md and SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md.

## Delta

- Repaired defect: an approval-required turn published terminal epic failure and
  released admission; approval continuation then conflicted with that publication.
- Required behavior: preserve unfinished parent and child authority through a
  retained `epic_approval_pause.v1`; consume it once after resolved decisions and
  continue the original request, or close denial without an effect.
- Retain pause history in the existing epic journal. Do not overwrite terminal
  outcomes, invent success, reset cards or weaken the original checkpoint checks.
- Engine, epic and governed turn composition now share the control-plane path
  beside an absolute selected runtime DB. The old engine ignored custom DB selection and
  looked in the global durable store, causing missing-target continuation failures.

## Migration Plan

1. Existing terminal records remain immutable. No old failure is backfilled as a pause.
2. New pause records are additive; the journal must travel with existing retained stores.
3. Validate same-process/restart approval and denial, pending refusal, duplicate and
   concurrent continuation, changed bindings, actual effects and parent/child truth.
4. A consumed pause interrupted before further evidence remains uncertain and refuses redispatch.
5. Preserve previously split global/custom control-plane stores. No automatic
   merge, migration or historical-kernel continuation is claimed by this cutover.
6. Relative runtime SQLite paths still use the process directory while the
   control-plane binding retains the workspace base. Absolute DB paths define
   this repair's verified scope; relative path convergence remains BT-5 work.

## Rollback Plan

1. Stop new execution if admission, request, checkpoint or outcome truth diverges.
2. Preserve journal, runtime/control-plane stores and artifacts before reverting code.
3. Older code cannot resume new pauses; never erase retained authority to force execution.

## Versioning Decision

- Local 0.6.2 remediation candidate; no release/version/tag is created here.
- The existing approval decision routes and selected capability families remain unchanged.
