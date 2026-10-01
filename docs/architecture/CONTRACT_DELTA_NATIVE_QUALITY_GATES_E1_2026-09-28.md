# Native checker enforcement in Quality

## Summary
- Owner: Orket Core
- Date: 2026-09-28
- Affected contract: `docs/specs/QUALITY_CHECKER_CONTRACT.md`.
- Status: implemented; missing-command opening retained, native gates and regression closing pass.

## Delta
- Both truthful-checker steps currently run checker regressions without running
  the actual taxonomy or critical no-op gate over the repository.
- Add strict taxonomy and the default-root no-op command to both existing steps.
  Preserve every previous selector, the explicit coverage configuration and 89
  percent floor. Add the workflow guard to both regression selections.
- The guard checks exact native argv in each named, mandatory step. Comments,
  echoes, same-line compound syntax, another job and narrowed roots cannot satisfy
  the inspected command. Other shell flow or failure masking is not evaluated.
  Existing prefix/pytest-selector observations retain their previous behavior.

## Migration Plan
1. No runtime, artifact, marker or checker-output schema changes are required.
2. Apply workflow, guard and contributor/contract wording together. The authority
   manifest checker belongs to its separately coordinated E2 cutover.
3. Run the guard against the unchanged workflow first for a valid opening, then
   apply the workflow and rerun it with checker regressions and both native gates.
   Run canonical Ruff and retain complete-suite coverage and hosted Quality as
   separate acceptance obligations. Record source-bound results in the plan.

## Rollback Plan
1. If command admission or a guard regresses, restore the affected change and
   retain the missing automation as open debt; do not weaken strict semantics.
2. No persistent data migration is involved.

## Versioning Decision
- No package version change is assigned by this candidate.
- Contributor and automation enforcement changes; runtime compatibility preserved.
- Structural workflow success does not establish runtime or hosted Quality truth.
- The 278-case source closing includes the workflow/checker regressions. The same
  5,520 inputs pass strict collection of 10,902 cases and the native no-op check
  over 703 files with zero findings/errors. Full coverage and hosted acceptance
  remain separate. The E2 source checker is now retained in both steps too.
