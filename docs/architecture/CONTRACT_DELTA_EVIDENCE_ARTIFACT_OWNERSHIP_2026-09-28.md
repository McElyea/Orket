# Evidence artifact ownership contract delta

Status: Implemented; 45 source closing controls and selected existing guards pass
Date: 2026-09-28
Owner: Orket Core
Contract: [Evidence artifact publication ownership](../specs/EVIDENCE_ARTIFACT_PUBLICATION_OWNERSHIP.md)

## Implemented change

Two application artifact authorities acquire one retained I/O attempt per public
operation using the existing shared owner. Sandbox terminal export renders the
document to immutable JSON text before yielding; outward publication captures rendered nested payloads,
and outward verification captures all reference/digest pairs. Relative paths bind
to admission cwd before native work begins.

Previously, cancellation could complete a public coroutine while a raw worker or
file context still had work outstanding. Outward payloads and verification pairs
could also observe later caller mutations. After this change, cancellation and
timeout wait for the admitted attempt to settle. Native failure retains precedence
according to `run_owned_io(..., preserve_failure=True)`.

Existing schemas, redaction helpers, digest/naming rules, output locations,
exclusive admission files, legacy aliases and write sequence remain canonical.
The writer may finish its already-admitted ordered batch after cancellation; this
is an intended lifecycle change, not an atomic-file-set or durable-success claim.
Malformed borrowed payloads may now fail during pre-await capture/rendering rather
than after native path discovery; no new validation vocabulary is introduced.

## Authority and compatibility limits

- Sandbox terminal truth still belongs to the lifecycle/terminal service and its
  retained records. A complete artifact after cancellation does not advance it.
- Outward proposal/model admission authority still belongs to existing retained
  admission, approval and ledger transactions. Artifact files do not authorize work.
- Partial output, legacy overwrites, exclusive-create refusals and absent automatic
  rollback/retry remain observable. No recovery or compatibility shim is added.
- Default terminal-root construction, outward policy-validation ownership, broader
  storage lifetime, TLS/provider correctness and whole-D closure remain separate.
- Real local artifact opening and closing evidence is retained below. External
  model execution, Docker behavior and whole-D closure are not claimed.

## Observed opening and closing

The original 45-case source opening observed 37 failures and 8 passes: outward
publication/verification had 24 failures and 6 passes; sandbox evidence had 13
failures and 2 passes. Failures reached early-return, incomplete/unclosed file
effects, or borrowed-input/path assertions. The partial-publication case failed
during repeated cancellation before its later exclusive-scope refusal assertion;
it is an adverse ownership case, not an ordinary refusal regression.

The original sandbox terminal timeout pass did not observe deadline cancellation
before releasing the native hold. The fixture correction requires exactly one
actual cancellation request on the supplied task and pending caller/waiter state
after sibling SQLite progress, before release. The unchanged-product timeout-only
opening then failed all 14 cases at that ownership assertion, with 31 deselected
and process exit 1. All 5,504 bound inputs stayed unchanged. This correction does
not rewrite or count the earlier ambiguous pass as retention proof.

Retained source-local evidence:

- `.tmp/goal-20260928-remediation-opening-readback.json`, corresponding XML/log:
  original 99-case campaign, including all 45 evidence controls.
- `.tmp/goal-20260928-evidence-timeout-opening-v2-readback.json`, corresponding
  inputs/XML/log: corrected 14-case timeout opening.
- `.tmp/goal-20260928-evidence-opening-audit/REVIEW.md`: exact failure review,
  fixture change, baseline/report hashes and interpretation limits.

All 45 closing controls and selected existing guards pass in the combined
512-case Windows Python 3.11 run, exit 0 in 227.69s. All 5,509 inputs remained
unchanged. Evidence: `.tmp/goal-20260928-remediation-closing-v1-readback.json`
and corresponding inputs/XML/log. The deadline cases use the strengthened fixture.
No full-suite, installed-platform or coverage pass for this changed source is implied.

## Versioning decision

Patch-level lifecycle correction on the development candidate after 0.6.114.
Effective date: 2026-09-28. This change does not bump or publish the version and
requires no stored-data migration. Reverting reopens the admitted-operation
lifetime/input-binding defects; retained partial artifacts and failed observations
must not be deleted to simulate rollback or acceptance.

## Required same-change routing

Root must add the new contract to `docs/README.md`, record the precise opening
and closing observations in the active architectural-truth plan, and route the
current authority snapshot to the applicable contract without duplicating this
definition. Mark the contract Active only with the applied implementation and
accepted native controls; retain any failed opening/candidate observations.

If the E2 authority cutover also proceeds, preserve the final pre-cutover snapshot
after these accepted observations are recorded. That cutover separately needs the
full flat `orket.runtime.<module>` alias-family obligation routed through
ARCHITECTURE; the earlier provider-only compatibility record is insufficient.
