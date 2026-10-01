# Bounded current authority index

## Summary

- Change title: replace the mixed current/history snapshot with a bounded generated index.
- Owner: Orket Core.
- Date: 2026-09-28.
- Affected contract: `docs/specs/CURRENT_AUTHORITY_SOURCE_CONTRACT.md`.
- Status: applied; actual-root checks and consumer/adverse controls pass.

## Delta

The existing `CURRENT_AUTHORITY.md` mixes canonical routes with dated observations
and a separately maintained embedded JSON payload. The replacement authors at most
40 current records and 32 KiB in `docs/architecture/current_authority.json`; one
validator and renderer produce the public snapshot. Canonical policies, contracts,
start-path definitions and implementation ownership stay in their existing sources.
The 39-record initial index names ten commands, ten canonical references, two
execution boundaries, eight active contracts, four compatibility entries, three
claim ceilings and two unavailable proof scopes. It does not adopt the earlier
711-source scratch catalog or a separate document-status registry.

The source validator binds documented argv to actual declared entrypoints. It
reports structural validity separately from current execution proof, which remains
unavailable without a portable evidence adapter. This cutover establishes neither
runtime compliance nor complete E2 acceptance.

## Migration Plan

1. After the frozen full-suite run settles, copy the exact final pre-cutover authority
   bytes to the tracked history path and replace the manifest's application-time
   hash placeholder with their SHA-256. Preserve all earlier proof records.
2. Review the old current obligations against existing contracts, the active plan
   and exception register. Extract any otherwise ownerless durable obligation
   before generating the replacement. Do not promote historical observations.
3. Apply the new manifest, tools, source contract and consumer tests in one change.
   Update CONTRIBUTOR with the author/regenerate/check workflow and install the
   actual source checks and native controls in both Quality selections.
4. Run render, check, explicit current-proof refusal and adverse controls against
   the applied Git-visible sources. Run docs hygiene, dependency, no-op, taxonomy,
   canonical Ruff and applicable Quality gates. Preserve failed observations.
5. Keep the existing API, CLI, orchestrator, dispatcher, message and evidence
   extraction order and parity requirements. Index generation does not close them.

## Rollback Plan

If source parity or obligation routing is wrong, preserve the failed manifest and
observations, then restore the reviewed pre-cutover view and its authoring workflow
together. Do not edit the generated file to conceal a failing source check. Historical
data is retained byte-for-byte; no runtime or persistence migration occurs.

## Versioning Decision

This changes the authoring contract for the authority snapshot and its consumers,
not the product runtime or wire API. The cutover is applied after 0.6.114 without
assigning a version or claiming a release. Exact history is 325,283 bytes with
its SHA-256 retained in the manifest. The initial generated view is 89 lines;
actual-root render/check passes and the current-proof request returns exit 1.
The four compatibility rows include the complete flat runtime alias family,
with its exact removal version still unassigned. Consumer/adverse controls pass
in the 278-case source closing selection with all 5,520 inputs unchanged; the
same inputs pass canonical Ruff, strict taxonomy, dependency, no-op and docs
hygiene gates. Runtime, full coverage and hosted acceptance remain separate.
