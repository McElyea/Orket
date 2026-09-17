# Extension capability worker lifetime

## Summary
- Owner: Orket Core; date: 2026-09-13.
- Authority: `docs/specs/API_RUNTIME_LIFECYCLE.md`.
- Trigger: cancellation and asyncio timeout settled extension calls while their
  executor workers could still write or fail.

## Delta
- Model availability, STT/status probes, TTS discovery/synthesis and voice control
  share the existing cancellation drain through `run_owned_thread`.
- The current synchronous call settles before cancellation propagates. Repeated
  cancellation does not detach it. A worker failure takes precedence, with existing
  interface error mapping retained.
- Model generation and owned default-model cleanup use the same helper. Existing
  `run_owned_io` callers retain their default error/cancellation behavior.

## Migration Plan
1. Adopt the current core candidate with the existing SDK 0.7.0a1 pair.
2. Allow cancellation and shutdown to wait for a synchronous provider; an asyncio
   deadline cannot terminate its thread. Direct embeddings must stop admission
   and await their calls before closing resources.
3. Keep speech provider resource ownership with its embedding caller. No close
   protocol or SDK interface changes are introduced.
4. Retain the counterexamples and installed/TCP/Piper proof in the canonical plan.

## Rollback Plan
1. Stop affected admission if a synchronous provider cannot settle. Preserve
   unresolved effects and evidence instead of claiming successful shutdown.
2. Do not restore detached-worker cancellation or interpret thread drainage as
   termination of provider-created descendants.

## Versioning Decision
- Core behavior repair within the current unreleased candidate; no SDK/schema,
  release, tag or publication change.
- Native Piper descendant supervision, null-voice availability truth, stuck-thread
  termination and broader capability/resource conformance remain separate work.
