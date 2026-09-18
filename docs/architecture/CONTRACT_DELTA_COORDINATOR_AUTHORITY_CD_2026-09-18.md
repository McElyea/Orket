# Standalone coordinator ownership and explicit inputs

Owner: Orket Core
Date: 2026-09-18
Status: implemented scoped checkpoint; full-plan acceptance open

## Summary and delta

The unchanged 0.6.17 standalone coordinator constructed one FastAPI app, in-memory card
store and control-plane repository at module import. Import alone creates durable
directories. Its thread await can be cancelled after the real store claim while
the worker is still running, leaving a claimed card without its SQLite lease.
The store also retains callers' nested completion-result references. The original
observations are in `.tmp/c-coordinator-authority/before/` and bind unchanged
0.6.17 inputs. These are actual ASGI, thread, memory and SQLite observations.

Introduce an explicit `create_coordinator_app(...)` factory with one
application-owned coordinator service per application. Retire the module-default
app/store/repository aliases without a compatibility shim. The service selects
captured project/environment storage and runtime clock inputs. Interfaces own
HTTP request/error shaping; application owns card transitions, lease/reservation
publication and response projection. Existing response fields and the bounded
hedged/non-hedged authority distinction remain intact.

Capture nested request inputs before awaiting. Serialize admitted transitions
within one coordinator owner and retain each admitted transition through caller
cancellation until its real worker, control-plane publications and projection
settle. Closing stops new admission and waits for admitted work. Cancellation
does not roll back a completed transition or authorize another claim. Failures
remain observable rather than becoming a successful response or clean shutdown.
Per-operation monotonic and wall-clock observations must be explicit and shared
by store transition and publication preflight; do not clamp a reversed wall clock
or weaken existing lease timestamp invariants.

The in-memory card store and durable control-plane history are not one transaction.
This change does not establish crash recovery, multi-process coordinator sharing,
cross-process fencing or a hard shutdown deadline. Failure after a store mutation
must remain explicit, with no success claim. Existing drift preflights and
promotion-failure closeout must retain their fail-closed behavior. Hedged cards
must not gain invented non-hedged lease authority.

## Migration and validation

1. Patch checkpoint: 0.6.18. Replace standalone startup targets of
   `orket.interfaces.coordinator_api:app` with
   `orket.interfaces.coordinator_api:create_coordinator_app --factory` for an
   ASGI server supporting factories. Embedded callers retain the returned app
   and close its lifecycle; tests inject their own store/publication owners.
2. Replace module-global test coupling with explicit isolated app/owner fixtures.
   Preserve original behavioral assertions, including expiry takeover, hedged
   first completion, drift refusal and promotion rollback.
3. Prove import purity in a fresh process, isolated application roots/state,
   captured time/result inputs, real public claim/renew/expiry/complete/fail
   flows with SQLite, and cancellation/close while real store work is held.
   Establish the responsiveness bound at 0.5 seconds before measuring it.
4. Run affected application/API/worker regressions and fresh focused installed
   package proof. Broad Python/platform/provider/Quality acceptance remains a
   final C/D and whole-plan requirement, not a claim of this intermediate proof.

## Rollback and recovery

Rollback runtime and authority together if public parity or ownership regresses.
Preserve databases, failed observations and incomplete transition state. No
schema migration or destructive state repair is proposed. Reverting restores
the known cancellation and global-owner defects; it is not a safe-ownership claim.
Operators must not infer card state restoration from a failed/cancelled request.

## Observed checkpoint and durable authority

The active lifecycle contract is `docs/specs/COORDINATOR_RUNTIME_LIFECYCLE.md`.
Unexpected transition failure quarantines that owner: later requests receive
503 and close raises instead of claiming clean shutdown. Existing store errors
remain their expected HTTP refusals. The effect that failed can already have
changed the memory store or written durable history; no automatic repair is
admitted. The contract explicitly limits ownership to admitted application
transitions and requires separate roots for isolated control-plane history.

Observed path: primary. Result: success for this checkpoint; partial success for
the full goal. Source and fresh installed Windows/Linux Python 3.11 each pass
39 selected cases. Real local HTTP/ASGI, SQLite and held-worker observations
cover import purity, isolated roots, claim/renew/expiry/complete/fail, hedged
parity, captured result inputs, retained cancellation/close, concurrent renewal,
own-close refusal and failure quarantine. Existing in-memory publication tests
remain contract controls, not independent durable or provider proof.

The first five-case run retained three passes and two incorrect test expectations:
`active`/`released` instead of existing `lease_active`/`lease_released`. Tests now
use the authoritative enum; runtime vocabulary and clock invariants are unchanged.
The original inputs, fixture bytes and failures remain retained. Controlled
wall-clock reversal still fails closed; the historical host-clock cause and
stock-clock reliability remain unproven.

Fresh package parity covers 1,026 core Python files and 1,041 wheel package files.
Both installed cells verify actual imported origins, retained artifact bytes,
public CLI controls and owned process cleanup. Graph collection removes three
forbidden pairs, with none added; 29 pairs, one authority cycle and ten analysis
errors remain. Full Python/platform/Quality/provider and C/D/E/CAP acceptance
remain open. Exact declarations and observations live under
`.tmp/c-coordinator-authority/`; durable execution status remains in the canonical
architectural-truth plan. Commit and annotated tag remain local during work hours.

Final staged whitespace rejected one extra EOF newline in the extracted view.
The one-byte correction preserves its AST. The original source/package/native
proof and staged rejection remain intact; a fresh 39-case source and two-cell
installed cohort under `.tmp/c-coordinator-authority/final/` binds corrected bytes.
The local receipt is `.tmp/c-coordinator-authority/final/local-checkpoint.json`.
