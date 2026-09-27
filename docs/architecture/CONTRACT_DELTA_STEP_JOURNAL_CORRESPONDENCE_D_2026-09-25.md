# Resolved-step and effect-journal correspondence

## Summary
- Change title: Refuse governed continuation or terminal authority over a resolved orphan step.
- Owner: Orket Core.
- Date: 2026-09-25.
- Affected contract: `CONTROL_PLANE_TERMINAL_AUTHORITY.md`.
- Status: implementation contract for the 0.6.106 development candidate;
  acceptance and publication remain owned by the architectural-truth plan.

## Delta
- Published behavior: unresolved dispatch blocks terminal closure, and retained
  same-attempt journals prevent zero-count pre-effect misclassification. A resolved
  step without its journal can still pass the common execution/terminal gate.
- Required behavior: the existing state gate first preserves unresolved refusal,
  then requires every resolved current-attempt governed tool step to have a journal
  matching run, attempt and step. The caller passes its existing record repository
  or transaction; there is no second writer or repair path.
- Missing correspondence raises the caller's existing error type with run, step
  and `effect journal` before ordinary terminal/resource publication or reuse.
  Neither explicit nor inferred executed-step counts bypass the check.
- Step and operation identifiers remain distinct. Journal-only same-attempt
  evidence still requires post-effect failure classification; other attempts do
  not cover a current step. A genuinely empty attempt remains pre-effect.
- Explicit resume with an accepted resumable checkpoint retains the published
  reconciliation behavior: resolved orphan steps are uncertainty evidence for
  blocked closure, never continuation or success. The read-only admission and
  writer transaction share checkpoint and correspondence validation. Missing
  checkpoint acceptance and unresolved dispatch still refuse without writes.
- Separate-read routes do not acquire an atomic snapshot. No journal schema,
  digest, uniqueness rule, reverse correspondence or remote-effect guarantee is added.

## Migration Plan
1. Compatibility window: coherent published records retain their behavior.
   Split authority refuses ordinary reuse/closeout rather than inventing evidence.
2. Migration steps: supply the same existing repository to all five state-gate
   callers: execution/reentry, finalization, preflight, approval terminal reuse,
   and recovery. Recovery admits accepted checkpoint-backed uncertainty only to
   its existing blocked reconciliation, with no redispatch. Keep the existing
   transaction and resource owners.
3. Validation gates: real SQLite/physical opening with explicit/inferred/zero
   counts, actual approval denial, wrong run/attempt/step, multiple steps, recovery,
   terminal reuse, healthy distinct identifiers, unresolved-first precedence,
   journal-only/other-attempt/empty controls and all retained behavior. Source and
   installed proof remain required; proposed controls alone do not establish them.

## Rollback Plan
1. Rollback trigger: coherent execution is refused or a guard mutates authority.
2. Rollback steps: stop publication and correct the shared guard; preserve
   unresolved refusal and every failed/passing observation rather than bypassing it.
3. Data/state recovery notes: do not synthesize or rewrite historical journals.
   This correction adds no operator reconciliation endpoint or redispatch permission.
4. The first full .106 source run exposed an overbroad guard that suppressed the
   accepted blocked-reconciliation path. Its four failures remain retained.
   Correction restores that path and seeds damaged completed-history fixtures
   after coherent finalization; it does not relax ordinary closure or success reuse.

## Versioning Decision
- Version bump type: patch correction with stricter refusal of inconsistent authority.
- Effective version/date: 0.6.106 candidate / 2026-09-25, subject to integration.
- Downstream impact: missing-journal records need trustworthy reconciliation;
  caller-provided zero counts cannot manufacture pre-effect or success authority.
