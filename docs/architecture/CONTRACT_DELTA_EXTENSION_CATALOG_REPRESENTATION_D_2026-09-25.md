# Extension catalog representation correction

Status: Active scoped D implementation; closing and installed acceptance remain open.
Owner: Orket Core
Date: 2026-09-25
Contract: `docs/specs/EXTENSION_CATALOG_REPRESENTATION.md`

## Delta

The real SDK round-trip opening reached three differences after successful Git
installation, persisted catalog listing, process restart and SDK execution.
Install returned the literal string `None` for two absent workload contracts,
while catalog reads returned empty strings. Reads also inserted the legacy
`register` callable into an SDK record whose installed value was empty.

One SDK optional-reference normalizer now serves manifest and catalog conversion.
It changes only null to empty, preserving non-null conversion and trimming.
The catalog's register fallback is suppressed only for exact SDK records;
explicit nonempty metadata and legacy/unknown style behavior remain.
Manifest validation, agent negotiation, dispatch and catalog schema are unchanged.

A separate public-parser/physical-catalog counterexample found that valid generic
SDK custom contract references were retained by parsing but omitted by the writer.
The writer now persists each nonempty reference independently for exact SDK style,
after the existing strict agent branch. Empty rows stay compact; legacy/unknown
styles do not gain reference persistence. Reference interpretation and admission
remain with their existing authorities. The opening failed at physical reference
equality; the 37-case focused source closing and 73-case source cohort containing
both real Git install/restart profiles passed. Full source and final installed
acceptance remain pending.

## Migration and validation

No compatibility shim, rewrite or reinstallation is required. Callers comparing
complete install/list records now receive consistent values for absent SDK
fields. Persisted legacy entries retain their old semantics. Agent records still
require their validated nonempty contracts and declarations.

The prior long-path test explicitly documented the three old differences. Its
new assertion requires complete record equality and canonical empty values;
all physical files, Git receipt identities, bounds and cleanup assertions remain.
Old passing and failing observations retain their historical predicates and must
not be reinterpreted with the new metadata expectation. New source/native
readbacks must require zero differences and the new exact field values.

Required proof includes the complete real install/list/restart observation,
unchanged logging/process-reader consumers, callable style and optional-reference
controls, SDK/legacy/agent behavior, long-path installation, and source plus
installed CPython 3.11/3.12 acceptance. Ten physical files, three install Git
receipts and both serial child owners remain mandatory in the round-trip case.

## Rollback and retained effects

Lost metadata, changed legacy defaults or digest bytes, broadened SDK admission,
abandoned command cleanup or remaining complete-record differences block
publication. Repair forward through the existing parser/catalog/installation
owners. Retain all failed/passing evidence, referenced checkouts and catalog
bytes; a representational mismatch does not authorize deleting installed effects.

## Versioning and limits

This is a patch correction planned for 0.6.106. The prior 0.6.105 checkpoint and
its historical observation contracts remain retained. No claim is made here
for entrypoint-only discovery, live model inference, hostile containment, Linux,
whole-D/E/CAP completion or whole-lane acceptance.
