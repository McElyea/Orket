# Supporting connector and SDK diagnostic failure policy

## Summary
- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source closing passed.
- Contracts: `docs/specs/CONNECTOR_INVOCATION_TIMING.md`,
  `docs/specs/SDK_WORKLOAD_PROCESS_LIFETIME.md` and existing shared diagnostic policy.

## Delta
Outward interruption publication retains the existing shared diagnostic owner.
Unexpected native failures, including native cancellation and fatal exceptions,
preserve the selected connector exception and add `E_OWNED_DIAGNOSTIC_FAILED`.
Existing expected-failure fallback and its detailed non-secret note remain.
Notes use the base exception implementation; an overridden note hook cannot
replace the primary. The actual admitted append/handler still settles before
return. No effect result, delivery acknowledgement or recovery authority follows.

SDK uncertainty keeps its existing native owner and typed secondary protocol.
The final diagnostic supervision catch now includes `BaseException`. It retains
the exact secondary as `diagnostic_error` and the existing typed note; successful
publication after caller interruption retains the original caller cancellation
as that secondary. The selected typed uncertainty, cause and private exchange
remain. Generic diagnostic policy would discard that required secondary and is
therefore not substituted. The earlier SDK lifetime-observed fatal policy and
exchange-removal precedence remain separate obligations.

## Migration Plan
1. No public signatures, new owners, retry or compatibility shims.
2. The original outward helper shadowed `logging.Handler.release` with an Event.
   Its 16 timeouts are invalid fixture evidence, preserved in opening v1. V2
   changes only the gate name/selection and preserves every assertion.
3. V2 opening: **9 outward failures/7 passes; 6 SDK failures/10 passes**. Eight
   outward cases exercise unexpected sink failure/marker policy; one supplied
   note-hook case guards arbitrary-primary preservation. Six SDK fatal cases
   fail the selected uncertainty/cause guard. All native child lifetimes settle;
   these are not process-escape claims. Report34 and composition7 also pass.
4. Closing: **697 passed across 63 selectors; 5,586 Git-visible inputs unchanged**; all 32 new cases pass with real child effects,
   physical append/standard handlers, exact primary/secondary observations,
   retained SDK request/result absence, independently reaped processes and
   healthy subsequent commands. Existing connector and SDK manager controls run.
   Evidence: `.tmp/goal-20260928-diagnostic-composition-opening-v2-*` and
   `.tmp/goal-20260928-epic-scheduler-composition-closing-v3-*`.

## Rollback Plan
Revert each bounded policy with its contract if identity, lifetime or retained
state changes; retain evidence and reopen the affected obligation. Inspect actual
effects and exchanges before retry. Do not erase diagnostic failures or uncertainty.

## Versioning Decision
Current 0.6.114 source candidate; no version bump. Proof is live local native/files/
process and declared controls, primary/success. Installed/Linux proof, required
producer input capture and whole D remain open. No provider or containment claim.


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
