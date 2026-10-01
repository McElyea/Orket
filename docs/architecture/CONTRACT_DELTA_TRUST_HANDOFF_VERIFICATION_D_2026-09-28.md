# Trust handoff native verification ownership

Status: Implemented; scoped Windows source closing passed; no version bump

## Summary

- Change title: trust handoff native verification lifetime and lexical package selection
- Owner: Orket Core
- Date: 2026-09-28
- Affected contract: `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`

## Delta

The current outward executor commits shared execution admission before directly
awaiting handoff verification. A raw to_thread await can abandon the verifier on
caller interruption; its relative package root is also resolved after dispatch.
No encompassing owner currently retains that native attempt.

Async handoff admission binds its package root with the existing lexical process
path authority and uses the existing shared native worker owner. The synchronous
verifier refuses loop entry before I/O. Offline CLI/native callers continue to
call the same verifier with unchanged report schemas, checks and rejection order.
The original declared package path remains in ledger events. Frozen scalar
verification context already captures scope/source/target inputs and is reused.

Cancellation or timeout waits for complete native verification and stream closure,
then publishes no verification or rejection event. Uncaught native error identity
takes precedence. Existing manifest OSError/parse tolerance remains a rejection;
later artifact read errors remain uncaught. No new verifier, copy algorithm,
retry, compatibility wrapper, policy or transaction authority is introduced.

Partial shared run/attempt EXECUTING state established before verification remains
retained after interruption/native error, without final truth or downstream work.
This is not transactional package capture or hostile-filesystem containment.

The integration selection uses actual emitted packages, real read/close holds,
repeated cancellation and observed wait_for deadlines, actual SQLite authority,
sibling database progress, ordinary error identity, current-directory rebinding,
drive-relative refusal and real offline CLI accepted/rejected flows. Existing
kernel/API admission guards remain in closing. Observed source closing is recorded below.

Canonical contract: `docs/specs/TRUST_HANDOFF_PACKET1_V1.md`.
Affected products: `trust_handoff_admission.py`, `trust_handoff_verifier.py`.
Root owns current-authority/workflow/project-plan updates and proof application.

## Observed opening

The 27-case unchanged-product selection reports **23 failed, 4 passed** in the
combined 157-case source campaign; 5,610 Git-visible inputs remain unchanged.
Eighteen interruption controls return before native settlement, two relative
package controls read the other directory, and two new native-entry/drive-relative
requirements refuse incorrectly. The actual corruption CLI additionally reports
MATH-CORR-008 as `ledger_export_partial_view` instead of the intended ordering
violation. That separate guard discrepancy was investigated and corrected below; it is
not evidence of this owner defect or a passing rejection-specific control.
Receipt: `.tmp/goal-20260928-trust-score-consumers-opening-v1-readback.json`.

## Migration Plan

1. No compatibility shim or grace period. Raw async embeddings must use owned
   native invocation; standard async admission performs it. CLI calls stay native.
2. Use absolute paths or ordinary paths relative to admission's invocation root;
   replace Windows drive-relative package paths with explicit absolute paths.
3. Retain the corrected real-package opening, native/CLI closing and existing
   kernel/API guards. Source inspection is not live acceptance.

## Rollback Plan

1. Roll back only if live controls expose an unintended admission/report change.
2. Revert this scoped composition/native-entry guard without altering package
   files or changing the existing verifier/rejection algorithm.
3. Preserve any already committed shared execution admission. No automatic
   rollback, terminal truth repair or inferred handoff acceptance is authorized.

## Versioning Decision

- Version bump type: none in this uncommitted remediation draft.
- Effective version/date: proposed after 0.6.114, dated 2026-09-28; scoped source proof passed.
- Downstream impact: direct event-loop verifier calls and drive-relative paths
  now refuse explicitly; native CLI reports and serialized event schemas remain.

The additional failure was an existing corruption-generator defect: swapping whole
rows violated the ledger's canonical key order, so the verifier correctly refused
before reaching approval ordering. The generator now exchanges only event type,
actor and payload within the original canonical slots, then uses its existing
rehash/rewrap path. No verifier or expected-rejection rule changed. The actual CLI
now passes all 23 corruption cases and its report-conformance case; the existing
nine offline ledger controls, including canonical-order rejection, also pass.
The scoped script Ruff observation retains two pre-existing unused-import findings;
canonical package/test Ruff is recorded separately, not claimed for that script.

## Observed source closing

All **330** selected Windows Python 3.11 source cases pass in 56.20s, with
**5,612 unchanged Git-visible inputs** and one upstream Starlette warning.
This includes all 27 trust-handoff and 14 score-root controls, retained kernel/API,
model-policy and ledger-order guards, direct logging consumers, typing regressions
and 30 workflow-gate checks. Evidence:
`.tmp/goal-20260928-trust-score-consumers-closing-v1-{inputs,readback}.json` and
sibling XML/log. Proof is live local native/files/SQLite/CLI behavior plus declared
contract/structural controls, path primary, result success. Current installed,
Linux, actual model inference and complete D/E acceptance remain separate.
