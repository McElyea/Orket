# Required command and fixture lifetime finalization

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: scoped Windows source closing passes; installed/platform acceptance pending.
- Contracts: `SHARED_IO_CANCELLATION.md`, `RUNTIME_VERIFICATION_OWNERSHIP.md`, `LOG_WRITE_SETTLEMENT.md`.

## Delta

Two raw Task/shield loops now use the existing shared settlement owner. The
finalizer entries discard only later caller cancellation after an outcome was
selected. Native failure and its cause remain exact, including native cancellation,
SystemExit and KeyboardInterrupt. No new loop, queue, state or diagnostic policy
is introduced. The native entry delegates to the shared async finalizer entry.

Command cleanup still precedes publication. Command OSError/ValueError/RuntimeError
publication failures remain causes of its domain cancellation; other native errors
propagate directly. Fixture publication failure still supersedes its caught
resource cancellation. Required fixture security publication retains normal
`run_owned_thread` semantics, so successful interrupted security publication still
propagates cancellation. Events do not authorize completion or recovery.

## Migration Plan

Use finalizer policy only after selecting the caller outcome. Normal resource
operations retain `run_owned_io`/`run_owned_thread`. The dependent outward UOW
uses finalizer policy only while a body/admission failure is already selected;
successful-body cleanup remains normally cancellable. Direct command workspace
selection and the other 17 inventoried publication sites remain separate work;
these two changes do not close all 19 producers' input/context contracts.

## Verification

V1 opening failed all 20 cases: its exact command/ready PID equality was invalid
for the Windows virtual-environment launcher. Original evidence is retained.
The corrected probe observes live ancestry and creation times to its isolated
caller, then independently checks the entire command/supervisor/transport chain
before releasing native acknowledgement. V2 reports **10 failed, 10 passed** in
26.08s, with 5,569 unchanged inputs. Two identity/cause guard assertions fail for
native cancellation; four SystemExit children exit 61 and four KeyboardInterrupt
children exit 3221225786. These compound guards do not separately report each
operand. All 80 process identities across 20 probes are absent before release.

The combined 38-selector closing passes **452** cases with 5,570 unchanged
inputs. It includes all 20 finalizer and 122 outward-store cases, real command and
fixture cleanup, physical append/readback, healthy subsequent commands, nested
fatal and admission controls, plus existing outward recovery guards. Exact
source/cases/results: `.tmp/goal-20260928-store-finalizer-closing-v1-*`.
Opening: `.tmp/goal-20260928-required-finalizer-opening-v1-*` and `-v2-*`;
audit: `.tmp/d-required-lifetime-finalizers-20260928/opening-v2/observed-audit.json`.

Proof is live local native/process/files/SQLite plus declared contract controls;
path primary, result success. No external provider, actual Docker, fresh installed
wheel, Linux or arbitrary eager/custom-task-factory acceptance is claimed.

## Rollback Plan

Drain admitted attempts before reverting callers and contracts together. Keep
append/cleanup receipts; reverting source does not undo physical effects or give
permission to retry uncertain work.

## Versioning Decision

Uncommitted correction after 0.6.114; no version bump or new authority admission.


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
