# API catalog observation ownership

## Summary
- Change title: retain system model-role and team catalog observations.
- Owner: Orket Core.
- Date: 2026-09-28.
- Status: implemented; 24 catalog controls and selected API guards pass.
- Affected contracts: `docs/specs/API_RUNTIME_LIFECYCLE.md` and
  `docs/specs/SHARED_IO_CANCELLATION.md`.

## Delta
- Previous behavior: the system router dispatched role/team discovery through raw
  `asyncio.to_thread`. Application request cancellation cancels its invocation
  child; that child can finish while the native catalog read remains active.
- Implemented behavior: `ApiSystemQueryService` selects filters and observations;
  `ApiWorkspaceReader` captures the model root and retains the existing
  `run_owned_thread` owner through native glob/read/decode/close. Native discovery
  lives in the storage adapter; pure role normalization/filter ordering has one
  core definition. No owner, proxy or compatibility export is added.
- Repeated request cancellation, elapsed caller timeout and application close
  retain the native operation. Cancellation after successful native settlement
  propagates; uncaught native failure retains shared-owner precedence. Existing
  `OSError`/`JSONDecodeError` skip behavior remains inside discovery and is not
  reclassified as publication failure.
- Why now: ASGI task settlement alone cannot establish native file settlement.
  The interface decomposition must not preserve this identified lifetime gap.
- Role normalization remains lower/strip/space-to-underscore without model-role
  aliases or hyphen conversion. Filters preserve first occurrence and bypass
  discovery when nonempty. Team roles remain sorted/deduplicated; filename
  fallback remains sorted without an added normalized deduplication step.
- Catalog path order, last collision winning, raw declared-role overlay lookup,
  seat/role ordering, department filter and response shapes remain unchanged.
  There is no atomic filesystem snapshot, added path containment, forced native
  stop or shutdown deadline. Partial/unreadable catalogs keep their prior meaning.

## Migration Plan
1. Compatibility window: none for the private interface helpers or router
   callback parameters; callers use the existing application query service.
2. Apply independently reviewed API parity extraction first, then this supplement.
   Migrate two fixture patches of `_discover_active_roles` to actual catalogs
   selected through `system_queries.reader.project_root`, seeded by the existing
   model-selection test helper. Neither endpoint test file grows. No aliases remain.
3. Apply only the new public integration controls against unchanged source for an
   opening counterexample. Their imports use existing public factory and helpers.
   Then apply the correction and run the same controls plus existing system/API
   lifetime, policy, operator and model-selection guards. Canonical Ruff,
   dependency, taxonomy and full coverage gates remain required.

## Rollback Plan
1. Trigger: changed catalog output, source admission or lifecycle regression.
2. Revert this supplement coherently across core/adapter/service/router/composition
   and migrated fixtures. Preserve opening failures and report the unresolved
   raw-worker gap; do not treat parity extraction as its correction.
3. Catalog operations remain observations; no storage migration or compensating
   catalog mutation is introduced.

## Versioning Decision
- Version bump type: patch at the next retained commit; no package version change yet.
- Effective version/date: dirty candidate after 0.6.114, 2026-09-28.
- Downstream impact: removed private helper/callback use requires migration.
  Public HTTP shapes and model selection semantics remain unchanged.

## Evidence and limits
- Opening controls record 12 ownership failures and 12 passing format/tolerance
  controls on Windows Python 3.11. Each ownership failure reached the held native
  read and observed early request settlement; fixture cleanup retained resources.
  All 24 closing controls and the selected API guards pass in the 512-case
  Windows Python 3.11 run, with 5,509 inputs unchanged. Source-local evidence:
  `.tmp/goal-20260928-remediation-closing-v1-readback.json` and its XML/log.
  No installed-wheel, Linux or live-provider acceptance is established for this
  changed candidate.
- The 12 interrupted ASGI cases hold genuine native reads with open descriptors
  across three discovery stages and four stop modes. Existing helper checks a
  responsive sibling SQLite operation, heartbeat, pending request/close owner,
  terminal request disposition and descriptor closure.
- Nine tolerant-file controls retain actual read plus injected `OSError`
  acknowledgement, actual malformed JSON and non-object JSON. Three additional
  public controls cover filter bypass, duplicate normalized filename fallback,
  and topology precedence/raw overlays/sorting. These do not prove TCP transport
  behavior, OS path fencing or remote provider effects.
