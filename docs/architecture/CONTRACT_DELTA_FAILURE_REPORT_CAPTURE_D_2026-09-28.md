# Failure report invocation capture

## Summary
- Change title: bind failure artifact and saved-log inputs before publication admission yields.
- Owner: Orket Core.
- Date: 2026-09-28.
- Affected contract: `docs/specs/FAILURE_REPORT_PUBLICATION.md`; original boundary remains documented in `CONTRACT_DELTA_CORE_EFFECT_BOUNDARIES_D_2026-09-14.md`.
- Status: implemented; scoped Windows source closing passed.

## Delta
- Previous behavior: the full publication already retained the shared owner and
  serializes report content before awaiting. The deferred publisher selects live
  `self.workspace` and resolves relative paths against a later CWD.
- Implemented behavior: capture workspace using the existing file-root authority,
  scalar identity and rendered document before the first await; pass only these
  concrete values to the existing owned publisher. Keep validation, I/O order,
  containment checks, required native saved-event publication and failure policy.
- Why required: service rebinding or CWD drift between admission and child/native
  execution can redirect a truthful failure artifact and its log to another root.
- Scope correction: report scalar identity is already frozen, so no supported
  scalar-mutation defect is claimed. Nested rendered-content/frozen-identity cases
  remain guards. No object.__dict__ or frozen-model bypass control is used.

## Migration Plan
1. No public signature change or compatibility shim. Standard `publish(report)`
   consumers continue to supply a frozen report and workspace.
2. Apply the new integration module first against exact unchanged source; retain
   the two real root-capture openings and Windows drive-relative refusal result.
3. Apply product/spec/delta and run all 34 new controls plus existing failure-value,
   core-effect and evaluator-admission controls. Native files/logs, closure,
   cancellation/deadline, partial acknowledgement failure and refusal remain real.
4. Source/installed/interpreter acceptance and shared authority/gates are separate
   scheduled work. Static candidate checks are not runtime proof.

## Rollback Plan
1. Trigger: changed report/event contents, ordering, failure policy or path admission.
2. Revert this bounded change and its contract update, retaining observations and
   reopening the selected capture obligation.
3. Do not delete reports or logs to hide a failed acknowledgement; inspect retained
   files before replaying diagnostics. No completion/recovery authority is created.

## Versioning Decision
- Version bump type: none for this remediation candidate.
- Effective version/date: current 0.6.114 source candidate, 2026-09-28; no release bump.
- Downstream impact: relative workspaces bind at invocation and drive-relative
  workspaces refuse. Prepared logging selection and standalone native fallback
  remain unchanged; broader logging environment/time capture is excluded.

## Observed source proof

The 34-case opening had **3 failures, 31 passes**: service rebinding, CWD drift
and Windows drive-relative refusal. Frozen identity, rendered nested content,
owned files/logs, failure precedence and refusal guards already passed. The
combined 50-case run also had 16 invalid outward-helper failures; those are not
failure-report findings. Its 5,578 inputs were unchanged. All 34 pass after the
correction, first in the 73-case diagnostic opening and again in the **697 passed across 63 selectors; 5,586 Git-visible inputs unchanged**
closing with existing core-effect/evaluator/value guards. Evidence:
`.tmp/goal-20260928-report-diagnostic-opening-v1-*`,
`.tmp/goal-20260928-diagnostic-composition-opening-v2-*` and
`.tmp/goal-20260928-epic-scheduler-composition-closing-v3-*`. Proof is live local
files/native logging and declared integration controls, primary/success.
Installed, Linux and broader required logging input capture remain open.


Subsequent Windows Python 3.12 **source** closing: **271 passed** across 12
selectors in 112.36s; all 5,586 Git-visible inputs were unchanged and equal to
the 697-case Python 3.11 closing snapshot. All 259 shared case identities pass;
the additional native-owner controls retain their own scope. This includes all
122 outward store, 20 finalizer, 18 epic cleanup, 34 failure-report, 32 supporting
diagnostic and seven component-construction controls. Evidence:
`.tmp/goal-20260928-new-ownership-source-py312-v1-*` and
`.tmp/goal-20260928-composition-ownership-parity.json`. All 4,956 historical
installed bindings remain unchanged. Reusing that environment's interpreter
with current source is not fresh installed-wheel acceptance. Linux, current
installed and broader quality/capability gates remain separate.
