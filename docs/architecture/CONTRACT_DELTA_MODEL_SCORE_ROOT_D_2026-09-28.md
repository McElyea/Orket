# Model score-report invocation root

## Summary

- Owner: Orket Core; date: 2026-09-28.
- Status: implemented; scoped Windows source closing passed.
- Existing model-selection owner: `docs/architecture/CONTRACT_DELTA_MODEL_SELECTION_CD_2026-09-17.md`.
- Related authority: `docs/specs/SETTINGS_INPUT_OWNERSHIP.md`.

## Delta

Model selection already captures its environment at service construction and
detaches supplied organization, preference and settings values at preparation.
Default readers and score reads use the shared native I/O owner. However, a
relative `score_source` reached the score worker unchanged. That worker's later
path resolution could select another current directory after a settings wait or
native admission. The digest described the bytes actually read, without binding
their directory to the preparation's invocation.

`ModelSelectionService.prepare` now selects the invocation directory at entry,
before default-reader or score-worker waits, through the existing file-root
capture authority. After unchanged compliance-policy selection, the existing
absolute-path policy anchors the report to that root. Native resolution, read,
close and digest remain one owned score observation. Each new preparation selects
its own root and reads fresh bytes; no construction-root binding or cache is added.

Preparation requires an observable current directory at entry, including when
later settings select an absolute report or no report. This explicit admission
change permits root selection before default settings reveal a relative path.
Root-capture failure propagates before default or score work. Windows drive-relative
reports such as `C:scores.json` refuse with
`E_PROCESS_DRIVE_RELATIVE_PATH_UNSUPPORTED`. Absolute reports keep their selected
root; a colon remains an ordinary POSIX filename.

Environment/provider precedence, explicit override, strategy validation and
advisory compliance demotion are unchanged. Missing, unavailable, invalid or
partial reports retain their existing status, warning, byte digest when available
and inline-score behavior. The score reader does not retry another directory or
provider. Caller interruption retains an admitted native worker until settlement.

Default settings/preferences keep their distinct observation and migration
contract. This change does not create an atomic two-file snapshot, refresh bound
settings or make arbitrary Python configuration hooks pure. The captured root
does not prevent later symlink/file replacement or provide hostile-editor
containment. Native observation remains the source of actual score provenance.

## Migration Plan

1. Public service signatures and callers remain unchanged. Relative report owners
   must intend the preparation-entry directory. Windows callers using drive-relative
   values must supply a normal relative or absolute report path.
2. Observe the unchanged-source opening before applying the product correction;
   repeat the same cases afterward. The proposed 14-case local integration
   selection covers real score files, CWD changes at preference/settings/score
   waits, absolute-path guards, repeated cancellation, timeout, native drive rules,
   missing/invalid/partial/unavailable reports and fresh preparation roots.
3. Retain existing model-selection, operator/compliance precedence, provider-default
   and API response guards. Supplied latency and settings contexts establish
   controlled local behavior, not actual model inference or natural performance.
4. Record observed failures, closing results and exact source bindings in the
   active remediation plan. The historical model-selection checkpoint remains
   scoped to its original source/installed/provider observations; it does not
   prove this subsequent root migration.

## Rollback Plan

If root selection, score provenance or selection semantics regress, revert this
bounded product/control/contract delta together and retain failed observations.
No persistent format or store migration is introduced. Preserve configured score
files and their observed bytes; do not replace evidence to obtain passing results.

## Versioning Decision

Unpublished development candidate after 0.6.114; no version bump. Local source
opening/closing, current installed/platform parity, actual-provider proof and
whole D2 acceptance remain separate. Structural review alone is not runtime proof.

Observed opening: **10 failed, 4 passed** on Windows Python 3.11; all 5,610
Git-visible inputs unchanged in the combined 157-case campaign. The failures are
nine relative-root observations and the newly declared drive-relative refusal.
Three absolute-path controls and per-preparation root reobservation pass. Receipt:
`.tmp/goal-20260928-trust-score-consumers-opening-v1-readback.json`.

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
