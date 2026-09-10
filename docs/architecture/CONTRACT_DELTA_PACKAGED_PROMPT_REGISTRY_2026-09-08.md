# Packaged Local Prompt Registry Delta

## Summary

- Change title: Package-owned default local prompt registry
- Owner: Orket Core
- Date: 2026-09-08
- Affected contract: default local-provider prompt registry location

## Delta

- Previous behavior: the default path was relative to the caller's working
  directory and its JSON file was absent from the core wheel. Clean installed
  live inference failed on its first model call.
- New behavior: the one authoritative JSON file lives at
  `orket/runtime/config/local_prompt_profiles.json`, ships as package data,
  and resolves beside the loader module. Explicit runtime-context and
  environment path overrides are unchanged and still fail closed if invalid.
- Reason: installed governed inference must not depend on a source checkout.
  No profile content, model selection, or fallback policy changes.

## Migration Plan

1. No compatibility copy or silent missing-file fallback is added.
2. Consumers of `DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH` need no change.
   Explicit references to the old repository path must use the new path or
   a separately managed operator registry. Historical archived docs retain
   their original paths as history.
3. Verify working-directory independence, clean wheel/source packaging, and
   actual installed single-model, multi-model, approval/restart and denial flows.

## Rollback Plan

1. Trigger: package-owned default causes a demonstrated regression.
2. Revert the relocation, default, package-data entry, and authority updates
   together; do not retain competing registry copies.
3. No durable run or effect records require migration. Interrupted proof runs
   remain recovery-pending; this change does not redispatch them.

## Versioning Decision

- Patch-level core packaging/runtime correction, pending normal versioned commit.
- Effective date: 2026-09-08; no release or publication performed by this delta.
- Downstream impact: explicit old repository paths require migration as above.
