# API reload process finalization

Status: Active
Owner: Orket Core
Date: 2026-09-27

## Summary

Retain cooperative console-signal handling through native finalization of the
dedicated reload worker. Contract: `docs/specs/API_RUNTIME_LIFECYCLE.md`.

## Delta

Uvicorn restores the signal handlers that preceded its serve scope. Previously,
an additional console signal after application shutdown could terminate the
worker before its native finalizers settled, making the launcher fail. The private
reload server now installs its existing cooperative handler before entering
Uvicorn, so restoration retains that handler until the dedicated process exits.
The supervisor still joins the worker and rejects every nonzero exit. A failing
finalizer is not normalized into success. No public embedding or wire API changes.

## Migration Plan

1. No caller migration or compatibility shim is required.
2. Both Quality jobs select native finalization controls alongside existing reload
   tests. They hold a real spawned worker after its event loop closes, send repeated
   console/group signals, release it and observe successful or failed native exit.
3. The canonical remediation plan records current platform/version proof. Older
   reload observations do not establish this new finalization behavior elsewhere.

## Rollback Plan

1. A supported Uvicorn signal-lifetime regression requires revisiting this private
   integration and rerunning real reload/finalization controls.
2. Reverting the handler installation restores the reproduced late-signal defect;
   do not claim finalization retention after such a rollback.
3. No durable data migration is introduced. Finalizer effects may already exist
   when a native failure is reported. This adds no forced-stop deadline.

## Versioning Decision

- Patch: 0.6.112, effective 2026-09-27.
- Compatibility preserved; audience: operators using canonical API reload.
- Whole-lane, installed-package and additional platform acceptance remain separate.
