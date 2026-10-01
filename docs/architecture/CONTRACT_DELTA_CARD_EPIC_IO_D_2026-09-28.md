# Card completion and epic journal native ownership

## Summary

- Owner: Orket Core.
- Date: 2026-09-28.
- Status: implemented; bounded source closing verification passed.
- Contract: `docs/specs/CARD_COMPLETION_ACCEPTANCE_CONTRACT.md`.

## Delta

Card metadata workers and final artifact capture could outlive interrupted callers.
Receipt SQLite closure and epic journal cleanup also lacked complete operation
ownership. Epic request/export values were borrowed across workspace resolution.
These paths now reuse the shared native I/O owner and lexical path capture.
Card observations and epic request/export dictionaries detach before native waits.
Receipt reads retain metadata, read-only SQLite closure and evidence inspection.
Final authorization retains artifact capture, including insufficient-evidence
diagnostics. Journal transactions retain parent creation, connection acquisition,
schema preparation, commit and rollback/closure; the exit stack retains connections
acquired before interrupted admission can return them to the caller.

An interrupted caller waits for admitted native work before observing its result.
Native failure keeps the shared owner's precedence. A journal body failure retains
identity through later cleanup cancellation; actual cleanup failure remains visible.
Required nested fatal settlement depends on `docs/specs/SHARED_IO_CANCELLATION.md`.
No caller-body ownership, automatic retry, effect rollback or new recovery authority
is added. Directory/schema effects and an already admitted commit can remain.

## Migration Plan

1. No compatibility shim or alternate owner is introduced. Relative paths bind to
   invocation cwd under existing `capture_file_roots`; unsupported Windows
   drive-relative paths refuse. Reconfigure owners explicitly to change roots.
2. Interrupted callers must inspect retained state before retrying. Existing
   admission, fencing, receipt sufficiency and explicit recovery remain authoritative.
3. Preserve the two new native ownership modules in both Quality jobs with existing
   card completion, epic admission/publication and approval recovery controls.

## Verification

The first unchanged-product opening returned 24 failures and 4 passes. Sixteen
failures were fixture setup: the artifact path omitted required `agent_output/`.
Correcting only those two fixture paths produced **21 failures, 7 passes**, with all
5,534 Git-visible inputs unchanged during execution. Native holds expose premature
settlement, changed cwd/request inputs and body failure displaced by cancellation.
Passing existing schedules are retained as controls, not claimed counterexamples.
Both original reports remain in `.tmp/goal-20260928-card-epic-opening-v{1,2}-*`.

The Python 3.11.14 source closing passed **287 tests** in 237.65 seconds (exit 0),
including all 28 opening identities and existing card completion, public turn,
control-plane, publication/recovery, approval continuation and nested-owner guards.
All 5,535 Git-visible inputs were unchanged; one upstream Starlette/httpx
deprecation warning remains. Canonical scoped Ruff passes. Evidence:
`.tmp/goal-20260928-card-epic-closing-v1-{inputs,readback}.json` and sibling log/XML.
Observed path: primary; result: success. Native file/SQLite/restart checks are live
local integration; workflow/admission checks retain their structural/contract scope.
The same 28 new cases also pass on Python 3.12.2 in 3.79s, with all 5,537 inputs
unchanged and one upstream warning. Product bytes and case identities match the
3.11 closing. The interpreter belongs to the historical installed campaign but
imports current source here; all 4,956 preserved historical bindings remain intact.
Readback: `.tmp/goal-20260928-card-epic-parity.json`. This is source proof.
The tests use real temporary files and SQLite,
with bounded native holds and independently observed connection closure and rows.
They establish no provider, live Docker, installed-wheel, hostile-path containment,
process-death recovery or complete repository quality result.

## Rollback Plan

1. A demonstrated admission, failure-selection or retained-state regression blocks
   acceptance; retain the failing evidence and correct the source candidate.
2. Reverting this change restores the exposed lifetime defects. Do not claim the
   affected interruption boundary as verified while reverted.
3. Preserve existing stores and journals; do not infer rollback or erase uncertain
   active admissions from a failed acknowledgement.

## Versioning Decision

- Source correction within the unreleased 0.6.114 candidate; no release is created.
- Public signatures and acceptance schemas remain. Cancellation settlement takes
  longer when native work is still running; native failure can win over cancellation.
- Custom filesystem replacement and arbitrary transaction-body work stay outside
  this ownership guarantee.
