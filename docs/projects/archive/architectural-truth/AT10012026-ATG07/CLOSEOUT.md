# ATG-07: Restore the unchanged coverage gate

Date: 2026-10-01 (America/Denver)
Status: Source gate passed; annotated checkpoint publication pending
Checkpoint: v0.6.124 on codex/architectural-truth-bt0

## What changed

Twenty-seven bounded batches add missing contract and runtime observations. Seven
reconciliations retain native Git-fixture correction, concrete peer-owner imports,
Windows path-identity consistency, and actual SQLite worker termination in the
process-death fixture. Containment still uses path ancestry; reference writes stay
forbidden. No runtime retry, lowered bound, coverage exclusion or added skip clears
a failure. The API timing interval and 0.5-second assertion remain unchanged.

## What was verified

The complete R07-worker-candidate campaign executed on Windows Python 3.11:
**12,964 passed, zero failed, 93 skipped, two warnings**. Its 13,057 XML cases equal
the strict collection count. Combined statement/branch coverage is
**89.21313183949974%**, above the unchanged **89%** floor. All Git-visible input
fingerprints remained unchanged. Observed path: **primary**; result: **success**.
This is live source execution, with individual unit/contract/structural limits
retained; it is not fresh installed-package proof.

All nine canonical preflights pass: Ruff, Mypy (1,222 sources), dependency direction,
strict taxonomy, critical no-op checks, project hygiene, authored and generated
current authority, and release policy. These are structural proof.

Native path diagnosis reproduced the Windows namespace mismatch. Four alias cases
failed before correction; the closing selection passes 87 cases and the native
replay passes 2,000 public writes. Native process diagnosis reproduced
SQLITE_IOERR_TRUNCATE while the actual worker survived launcher termination.
The corrected closing selection passes 101 cases, including 33 actual worker
deaths followed by recovery. All three death cases pass again in the complete run.

The earlier API timing failure remains recorded at 0.601391 seconds. The bounded
100-case diagnostic passes, and the final complete case passes at 0.136328 seconds.
The original outlier's cause remains unexplained; later observations do not erase it.
Earlier red campaigns, the native-recorder serialization failure and the diagnostic
harness's missing settings fixture are retained in [VERIFICATION.json](VERIFICATION.json).
Scoped totals overlap and are not added into a synthetic complete-suite result.

## What was not verified

Fresh Windows/Linux installations, actual llama.cpp inference and hosted Quality
are later ATG-v1 gates. The next Windows selection binds 467 selectors, 627 test
files and 6,234 cases to this passing source XML. Its three explicit localhost-Gitea
acceptance skips remain unverified. Thirty-four source-only AST/workflow checks are
retained separately. UNC identity contracts do not establish native SMB behavior
or hostile path-replacement containment. General current-authority runtime proof
remains explicitly unavailable.

## Remaining blockers or drift

The queue remains active. Default llama.cpp catalog access is unavailable and
hosted Gitea access is unestablished. Grounding residue normalization still removes
prose whitespace, and generic marshaller process interruption/descendant ownership
remains outside the frozen repair worksets. These findings do not enlarge ATG-v1.
No main merge, whole-lane retirement or minor-release readiness is claimed.

## Exact files touched and evidence

[VERIFICATION.json](VERIFICATION.json) lists exact files, source identities, scoped
and complete results, skipped cases, warnings, native counterexamples and raw local
receipt hashes. Raw ignored artifacts are not guaranteed to exist in another checkout.
Metadata-only closeout validation passes: version/release controls, docs hygiene,
current/generated authority and whitespace checks. Their scoped result is retained
in the verification receipt. Annotated checkpoint publication remains pending.
