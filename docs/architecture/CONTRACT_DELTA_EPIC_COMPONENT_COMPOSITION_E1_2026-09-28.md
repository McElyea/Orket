# Explicit epic component composition

## Summary
- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped source parity and fresh-process import checks passed.
- Existing public authority: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta
The private pipeline builder returns its constructed epic owner and required
approval service together. Dispatch uses the owner; resume uses the exact service
already supplied to it. The standalone owner's optional-service contract stays
intact. The constructor callable and keyword expressions retain their original
evaluation order. No cast, optional-value assertion, fallback or second service
construction substitutes for the explicit return type. Both production callers
and seven private fixture calls migrate to `_build_epic_run_components`.

Four epic-owner files and the pipeline use canonical same-domain execution imports.
Existing external flat aliases remain; no new compatibility export is added.

## Migration Plan
All repository private-builder callers migrate in the same change. Seven new
public dispatch/resume controls preserve constructor order/failure identity,
unchanged logical SQLite state and exact service identity. An adverse calendar
callback detects delaying the original owner-constructor lookup. These are real
composition/storage controls with supplied faults, not live-provider proof.
Baseline: **502 passed, 2 failed across 45 selectors; 5,584 inputs unchanged. The two additional direct Agent logging callers were repaired before product changes; all seven cases in that module then passed**. Closing: **697 passed across 63 selectors; 5,586 Git-visible inputs unchanged**.
Fresh processes check 22 epic bindings in 12 import-entry runs and 9 pipeline
bindings in 3 runs before/after. Wider source inventory remains unchanged within
each root-owned observation. No incidental import-cache population guarantee.
Historical isolated Mypy reductions remain structural observations; the current
canonical type gate and whole E1 are separate acceptance obligations.

## Rollback Plan
Revert private composition, consumers and imports together if service identity,
constructor order or public continuation behavior changes. Retain recovery data
and do not manufacture another approval service or continuation authority.

## Versioning Decision
Current 0.6.114 source candidate; no bump. Private builder name/tuple shape changes
without a compatibility shim; public signatures remain. Source parity is live
local integration plus structural/import proof, primary/success. Installed/Linux
and full typing/coverage acceptance remain open.


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
