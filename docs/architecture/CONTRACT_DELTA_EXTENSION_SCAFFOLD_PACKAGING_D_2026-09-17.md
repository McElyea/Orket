# Installed extension template authority

## Summary
- Owner: Orket Core.
- Date: 2026-09-17.
- Status: corrected full selected source and all four installed gates pass, including
  real console initialization, strict validation and existing-target refusal for both kinds.
- Trigger: all four initial API candidate installed cells returned
  `E_EXT_TEMPLATE_MISSING` for normal scaffolding. Source passed because the CLI
  located repository documentation beside its module. This was a shipping defect,
  not an omitted test-harness fixture.

## Delta
- Canonical authoring sources remain `docs/templates/external_extension/` and
  `docs/templates/governed_agent_external/`. Their shared kind/name mapping lives
  in `orket/core/contracts/extension_templates.py`.
- `scripts/governance/sync_extension_templates.py --write` derives the two archives
  under `orket/runtime/config/assets/extension_templates/`. `--check` rejects drift.
  The compiler uses Git-visible files, LF-normalized UTF-8 text, unchanged binary
  assets, sorted members and fixed ZIP metadata. Archives are generated delivery
  artifacts; edit their source templates rather than the archives.
- Source and installed runtime both consume these packaged archives. There is no
  source-checkout lookup or fallback beside site-packages.
- Application `extension_scaffold_service` owns kind selection and CLI results.
  `ExtensionTemplateStore` retains reading and materialization in an owned worker.
  It captures/validates all archive entries before writing, rejects path escape and
  duplicate target aliases, and verifies each output before reporting success.
- Existing targets still require `--force`; public flags and result fields remain.
  The `template` field now identifies the packaged archive. Unsupported kinds fail;
  missing assets retain `E_EXT_TEMPLATE_MISSING`. Corrupt assets cannot report success.
- Cancellation and caller timeout drain the admitted worker. A worker failure takes
  precedence. This is per-file verified publication, not an atomic directory
  transaction, process-crash rollback or fencing against concurrent external edits.

## Migration and verification
- Install the corrected core candidate to use scaffolding outside its checkout.
  SDK versions and generated template source semantics are unchanged.
- Maintainers regenerate and check archives after source changes and commit both.
  `docs/CONTRIBUTOR.md` owns that workflow; both Quality jobs enforce the check.
- Direct async embeddings await `create_external_extension`. The synchronous
  command entrypoint refuses a running event loop before performing I/O.
- `.tmp/c-api-inputs/initial-native.json` preserves the four identical three-failure
  observations. The source repair checks use actual files, cancellation barriers,
  injected post-publication errors and serialized unsafe ZIP names. The initial
  Windows backslash test accidentally normalized its fixture; that failure and its
  corrected serialized-header proof are retained separately.
- Fresh source/package/installed/console results belong in the canonical plan.
  This correction does not accept the complete architectural-truth lane.

## Versioning
- Corrected core `0.6.9` candidate; no SDK release or work-hours push.
