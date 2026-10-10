# Apache-2.0 licensing cutover

## Summary
- Owner: Orket Core
- Date: 2026-10-10
- Authority: `docs/specs/LICENSING_POLICY.md`
- Affected contracts: licensing, distribution metadata, contribution terms,
  core/SDK version boundary, retained source-wrapper compatibility.

## Delta
- Previous releases used BSL-1.1 with limited production rights and an eventual
  MPL-2.0 change license. SDK distribution metadata omitted the license.
- Orket original work now uses Apache-2.0 starting at the user-selected 0.8.0
  boundary across all Orket-owned package/template versions.
- Bundled MIT, ISC, and OFL-1.1 material retains its licenses and full notices.
- Core and SDK distributions ship checked license copies; package metadata and
  nested extension archives must agree with canonical source notices.
- The user authorized the minor version specifically for this cutover. This
  does not claim completion of an unrelated roadmap lane or waive release proof.
- Existing deprecated source-wrapper/rock aliases remain supported through
  0.8.x; no runtime API, protocol, or schema behavior changes.

## Migration plan
1. Install core and SDK 0.8.0 together to use the Apache release family.
2. Carry the supplied license/notice files when redistributing. Existing project
   state and older generated extensions are not rewritten automatically.
3. Verify fresh wheel/sdist contents, isolated installed commands, template
   generation/validation, and the unchanged applicable release gates.

## Rollback plan
1. Correct missing notices or metadata before publication. Retain failed artifacts
   and build a fresh candidate after correction.
2. Once published, issue a corrected release without replacing published bytes.
   A rollback cannot retract rights already granted under Apache-2.0.
3. Historical BSL releases and their original commitments remain unchanged.

## Versioning decision
- Core: 0.8.0 (`v0.8.0`). SDK: 0.8.0 (`sdk-v0.8.0`).
- Other Orket-owned package/template versions: 0.8.0.
- Compatibility: preserved; upgrade the matched pair for the new licensing terms.
- Effective boundary: the 0.8.0 source/release family; publication status and proof
  are recorded in `docs/releases/0.8.0/PROOF_REPORT.md`.
