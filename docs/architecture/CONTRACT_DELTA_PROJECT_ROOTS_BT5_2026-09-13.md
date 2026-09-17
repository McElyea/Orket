# Project-root authority cutover

## Summary
- Change title: Align operator discovery and execution with the selected project.
- Owner: Orket Core, architectural-truth BT-5.
- Date: 2026-09-13.
- Affected contract: `docs/specs/RUNTIME_PROJECT_ROOTS.md`.

## Delta
- Current behavior: discovery/driver defaults derive from the core package's
  parent. Installed reconciliation looks for `site-packages/model`; discovery
  and driver configuration also pass the model child to a loader that appends
  `model` itself. Scheduled wake admission lacks the timezone-data dependency
  needed on Windows and other hosts without a system IANA database.
- Proposed behavior: the invocation working directory supplies the default
  project. Discovery and driver configuration pass the project root to the existing loader. Explicit
  roots, execution workspace selection and packaged immutable assets retain
  their current precedence.
- Why required now: current installed llama.cpp proof records degraded startup
  despite a valid staged project; discovery and execution disagree on authority.
  The BT-5 ingress regression also fails on valid `America/Denver` schedules
  without `tzdata`; core metadata now declares it as a runtime dependency.

## Migration Plan
1. Compatibility window: no second fallback or package-relative alias is added.
2. Migration steps: retain existing assets; select the intended project through
   CWD or the existing explicit root. Do not move operator or package files.
3. Validation gates: pre-fix filesystem counterexamples, source and foreign
   Windows/Linux installed regression proof, unchanged package bytes, actual
   installed llama.cpp success and unsuccessful flows. Relative database history
   remains a separate required BT-5 migration and is not silently relocated.
4. Ingress dependency proof: install the declared core dependencies and exercise
   timezone gap/fold rules plus authenticated scheduled/webhook API admission
   through the retained queue and existing executor; no automatic timer or
   subscription is introduced.

## Rollback Plan
1. Trigger: discovery changes an unintended project, or explicit roots/packaged
   immutable assets lose their precedence.
2. Steps: stop the affected invocation and restore the prior code only after
   identifying the selected project and retained effects.
3. Data/state recovery: preserve all board and execution evidence; reverting code
   does not undo reconciliation effects or authorize deleting state.

## Versioning Decision
- Version bump type: patch candidate, subject to contributor commit/tag policy.
- Effective date: 2026-09-13; implementation/proof status stays in the canonical plan.
- Downstream impact: callers relying on installed-package-relative mutable
  projects must select that project explicitly. No release is performed here.
