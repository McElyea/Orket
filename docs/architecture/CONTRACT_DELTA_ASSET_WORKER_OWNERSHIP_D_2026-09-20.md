# Configuration and turn asset worker ownership

## Summary
- Owner: Orket Core, architectural-truth D.
- Effective version/date: 0.6.58 candidate, 2026-09-21.
- Contract: `docs/specs/REMAINING_RUNTIME_INPUTS.md`.

## Delta
Agent configuration currently runs in an unowned thread: cancellation and timeout
return while its actual native file remains open. Turn preparation catches an
async loader's TypeError and retries through a synchronous loader, duplicating an
already admitted operation. A sync-only loader also blocks the event loop; the
retained real dispatch/SQLite probe exceeds the declared 0.5-second bound.

Reuse `run_owned_thread` for Agent configuration and existing sync-only asset
adapters. Retain workers through interruption, preserving worker failures. Select
an async loader once and propagate its exception; do not infer signature mismatch
from TypeError. Do not change the admitted operation's timeout or add a fallback.

## Migration and rollback
Correct async and sync-only loader signatures remain supported. An async loader
must return its value or raise its actual failure; it cannot use TypeError to
request a second invocation. Existing Agent configuration locking and cached
state, card transitions and failure classifications remain. Rollback reintroduces
early-return and retry gaps and must disclose them; no earlier data is rewritten.

## Versioning and verification
Compatible patch. Retain native-file cancellation/timeout/failure and actual
card/asset/SQLite counterexamples, then verify responsiveness, repeated interruption,
failure precedence and teardown through public paths and installed regressions.
Synchronous configuration entrypoints, remaining D/E/CAP and lane acceptance stay open.
