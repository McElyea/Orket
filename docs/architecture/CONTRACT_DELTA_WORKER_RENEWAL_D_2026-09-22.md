# Worker native entry and renewal lifetime

Date: 2026-09-22
Owner: Codex for Orket Core
Status: Scoped implementation contract; acceptance recorded in canonical plan
Canonical contract: [Worker renewal ownership](../specs/WORKER_RENEWAL_OWNERSHIP.md)
Canonical acceptance: [Architectural-truth remediation plan](../projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)

Previously the D3 Worker adapter used synchronous HTTP/sleep without mechanical
native guards. Its daemon renewal thread was joined only after normal work; work
failure could detach it, and renewal exceptions could be lost before completion.

Require native entry before blocking effects and retain one renewal owner through
every exit. Surface renewal failure before completion while preserving coordinator
lease, hedging and terminal-result authority. Async use requires an owned worker;
the borrowed HTTP client remains its caller's resource with finite request bounds.

Already accepted server effects can survive failure or cancellation. No new lease
authority, completion verifier, client termination fallback, provider acceptance or
whole-lane retirement is introduced. Canonical D2 input and D3 reachability work
continues independently of the retained Linux clock blocker.

## Migration and validation

Effective version: 0.6.88 (pre-1.0 patch checkpoint with an explicit breaking contract).
There is no compatibility shim. Native callers retain their existing API. Event-loop
callers use `run_owned_thread` with the synchronous invocation. Keep the borrowed
client open until it settles and supply finite client request bounds. Handle work
and renewal exceptions; do not infer success from an accepted claim or `run_once`.
Validation requires refused blocking entry, real HTTP/SQLite renewal and failure
effects, cancellation/timeout retention, unchanged lease/hedging controls and
matching source/installed Windows proof. Synthetic guards are contract proof only.
The canonical plan records observations and outstanding Linux/full-suite limits.

## Rollback

A confirmed behavior regression blocks publication. A later regression requires
reverting this scoped change and its authority/version records together, then
repeating the affected proof. Do not restore event-loop blocking or detached renewal
as a silent fallback. Already accepted coordinator publications remain authoritative;
rollback of code cannot undo them and no state schema migration is introduced.
