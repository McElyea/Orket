# Contextual architectural size inventory

## Summary

- Owner: Orket Core. Date: 2026-09-27.
- Contract: `docs/specs/QUALITY_CHECKER_CONTRACT.md`.
- The canonical architectural-truth baseline uses Git-visible Python sources and
  reports complete oversized inventories with nested-definition context.

## Delta

The old size collector walked every Python file under `orket/`, including ignored
files, and retained only the largest 25 rows. Its unqualified inclusive spans did
not distinguish nested router functions from their containing factory.

The v2 size payload uses the existing shared Git inventory and preserves the
400-line file and 70-line function thresholds. Complete oversized lists accompany
the largest-25 summaries and source hashes. Function records identify enclosing
scopes, qualified names, direct nested definitions and observed route-decorator
syntax. Inclusive parent/child spans overlap; they are not independent defect
counts. No decorator-based exemption or runtime routing claim is introduced.
Git discovery, empty inventory, source parse/read and observed source mutation
fail collection instead of becoming an empty successful inventory.

## Migration Plan

1. The baseline command, stable output path and diff-ledger behavior remain intact.
   Existing size totals and largest-summary fields remain available.
2. Consumers needing complete comparison use `files_over_400` and
   `functions_over_70`; they must respect `collection_ok` and both error lists.
3. Native Git/file contract controls cover ignored/untracked admission, encoding,
   nested routers/classes, complete lists, refusal and in-scan changes. Full
   baseline execution remains a separate observation in the remediation plan.

## Rollback Plan

Revert the baseline call and collector together if reported identities/spans drift.
Retain prior reports and disclose restoration of incomplete/context-free inventory.
There is no runtime data migration and no reduction of size debt by recollection.

## Versioning Decision

Additive nested size schema `architecture_size_inventory.v2`; the outer baseline
schema and existing output location remain unchanged. Included in the next patch
checkpoint. This tooling correction does not establish runtime acceptance.
