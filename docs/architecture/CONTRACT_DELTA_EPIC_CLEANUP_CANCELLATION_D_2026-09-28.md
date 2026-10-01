# Epic journal native cleanup cancellation

## Summary
- Change title: distinguish native cleanup cancellation from later caller interruption.
- Owner: Orket Core.
- Date: 2026-09-28.
- Affected contracts: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md` and existing `docs/specs/SHARED_IO_CANCELLATION.md`.
- Status: implemented; scoped Windows source closing passed.

## Delta
- Previous behavior: the journal's cleanup catch suppressed every `CancelledError`
  after a body/admission failure, including an actual native rollback/close failure.
- Implemented behavior: when a body/admission failure is selected, use the additive
  shared `finish_owned_io` result policy. It retains the native result/failure
  through the existing settlement loop and ignores only later caller cancellation.
  With no selected failure, ordinary shared ownership still reports interruption.
  Native cleanup failure supersedes the original body error with its context;
  successful cleanup retains the body error. The original native cancellation
  remains observable directly or as the normal deadline wrapper's cause.
- Why now: close the failure-precedence gap in this goal's journal ownership change.
  Preserve migration/preparation, transaction body identity, SQL, rollback/close,
  retained admissions and all existing recovery/publication authority.

## Migration Plan
1. No compatibility shim or schema migration. Apply the separately reviewed
   additive shared finalizer helper before this bounded journal product change.
2. First apply only the new integration module against exact unchanged journal
   bytes, with the exact UOW v2 native fixture helper. Retain the original opening.
3. Run the 18 native controls plus existing journal/admission/publication guards
   after application. Tests hold real rollback/close; observe native identity,
   exact deadline cancellation, repeated cancellation, sibling SQLite progress,
   closed/joined workers and actual unchanged/committed admission records.
4. Native source/interpreter and installed gates remain separately scheduled.

## Rollback Plan
1. Trigger: changed failure selection, body ownership, retained effects or cleanup.
2. Revert this bounded change with its contract update, keep evidence, and reopen
   the exact obligation. Do not accept a substituted cancellation outcome.
3. Preserve journal rows and inspect them before reentry. Interrupted committed
   initialization markers remain durable; an exception does not undo admission.

## Versioning Decision
- Version bump type: none for the remediation candidate.
- Effective version/date: current 0.6.114 source candidate, 2026-09-28; no release bump.
- Downstream impact: the original native cleanup cancellation is now retained;
  no new automatic retry, recovery, release or workload completion authority.

## Observed source proof

Opening: **6 failed, 12 passed** in 1.55s, 5,573 unchanged inputs. The six native
rollback/close cancellation failures after a failed body were suppressed. All
18 pass in the later closing: **697 passed across 63 selectors; 5,586 Git-visible inputs unchanged**. The earlier 427/19
combined run also passed these 18; its unrelated caller failures remain recorded.
Evidence: `.tmp/goal-20260928-epic-cleanup-opening-v1-*` and
`.tmp/goal-20260928-epic-scheduler-composition-closing-v3-*`. Proof is live native
SQLite and declared integration guards, primary/success. Installed and Linux
acceptance remain separate.


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
