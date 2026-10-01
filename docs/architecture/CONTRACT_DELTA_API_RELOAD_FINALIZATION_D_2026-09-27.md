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
reload server installs its existing cooperative handler before entering
Uvicorn, so restoration retains that handler after the server loop returns.
The supervisor still joins the worker and rejects every nonzero exit. A failing
finalizer is not normalized into success. No public embedding or wire API changes.

### Interpreter teardown correction, 2026-09-28

The retained complete-suite failure exposed a later window: all three ASGI
shutdowns completed, but the final worker exited with Windows
`STATUS_CONTROL_C_EXIT` (3221225786). CPython resets callable signal handlers to
OS defaults before its final garbage collection. Native `SIG_IGN` survives that
reset ([CPython 3.11 signal teardown](https://github.com/python/cpython/blob/v3.11.14/Modules/signalmodule.c#L1642)).
Keeping a Python handler alone therefore did not establish process-exit retention.

The dedicated worker now switches handled signals to native ignore in `finally`
after the server loop settles. During serving, signals still request cooperative
shutdown. During finalization the parent remains the owner, joins the worker and
rejects every nonzero exit; no cleanup deadline or failure normalization is added.
This preserves the existing public contract and requires no caller migration.

The permanent controls also hold the actual interpreter's final garbage collection
after observing both interpreter finalization and cleared Python signal handlers.
They send real console/group signals and require the worker and launcher to remain
pending until release. Deliberate finalizer exit 17 must still fail the launcher.
The earlier multiprocessing-finalizer controls remain, as do real file-triggered
reload, held ASGI lifecycle and failure controls. Fixture setup failures are not
accepted as product counterexamples; the canonical plan records the exact retained
opening and closing observations and platform/version limits.

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
