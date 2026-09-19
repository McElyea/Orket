# Owned interaction lifecycle

## Summary

Owner: Orket Core. Effective date: 2026-09-19. Version: 0.6.31.
Affected contracts: interaction admission, finalization, workload dispatch and teardown.
Status: implementation candidate; full architectural-truth acceptance remains open.

## Delta

Application `orket.application.interactions` owns session/turn state, workload
admission, cancellation, commit coordination, queries and subscription lifetime.
Core owns stream vocabulary and packet1 context values. Storage publishes commit
and trace files; the stream bus remains an adapter. Retired adapter manager,
contracts, context and cancellation modules have no compatibility aliases.

Managers require an absolute project root matching their commit orchestrator.
Composition supplies runtime clocks/identities and a captured stream-enable flag.
API composition uses its supplied environment snapshot, including an explicit
`ORKET_STREAM_EVENTS_V1` and stream queue limits; missing enablement means disabled even if the process environment
differs. Direct construction defaults to disabled and uses `RuntimeInputService`
unless explicit inputs are supplied. Nested session/turn inputs and commit values
are captured before awaiting. Reused identities cannot close an existing owner.

Admitted transitions serialize per session; independent session/query work can
proceed. Cancellation waits for acceptance publication and then interrupts and
finalizes an unadopted turn with `fail_closed:admission_interrupted`. It never
reports that unexecuted workload as successful. Session-start interruption drains
the started hook and closes/unregisters the unadopted session. Publication/storage
failures take precedence over cancellation when cleanup cannot be verified.

Finalization retains one attempt per turn. Concurrent callers observe that same
attempt; retries observe its success or its retained failure, rather than a
fabricated pending handle. A failed attempt blocks the session and requires
inspection; it is not automatically redispatched. Successful handles now return
`status: committed` after verified commit/trace publication and stream delivery.
This describes publication; a committed decision can have `commit_outcome:
fail_closed`. It does not imply successful workload effects.

HTTP admission adopts the workload into the API lifetime before returning the
turn ID. Before that transfer, interrupted dispatch closes the turn as failed.
After adoption, response loss does not cancel the application-owned workload.
Public finalize refuses a managed workload that has not published its result.
API shutdown first cancels/drains admitted invocations and workloads, then closes
interaction sessions and unregisters them. Direct session close refuses a still
running managed workload: drain its application owner first. Shutdown/session
close failures remain failures and retain inspectable state.

Workload contexts cannot author lifecycle events or authoritative claims. Their
`emit_event` returns false for a canceled turn or best-effort transport drop;
otherwise it returns true after publication. Detaching a subscriber releases a
blocked publisher and joins its delivery waiters; this is not acknowledgement
from a disconnected consumer. Finalized non-canceled turns refuse
later events. Commit intents are frozen and cannot be appended after finalization
admission. Existing operator cancellation still means an observed state/stream
transition and audit; it does not certify that every external effect has stopped.

Unexpected queue restoration failures propagate instead of silently losing another
turn's events. The direct provider-scenario CLI owns its runner, detaches its
subscriber and joins cleanup before producing its verdict; stub scenario proof
does not establish live provider acceptance.

Commit files remain at
`<project>/workspace/interactions/<session>/<turn>/authority_commit.json`, with
the existing deterministic digest and intent schema. Trace files remain beside
them. Each file uses native nonblocking ownership, same-directory replacement,
flush/sync, closed-file readback and exact-content conflict checks. Matching files
can be reobserved; differing files are refused, never overwritten as a retry.
Preserve `.owners/` directories beside these files. Busy native ownership refuses
the operation. Diagnostics and stream messages do not override durable contents.

These are separate file, stream and state effects, not one transaction. Failure
can leave an artifact or partially delivered stream; inspect it before recovery.
No restart reconstruction of in-memory sessions, exactly-once workload execution,
hostile-editor fencing, remote filesystem guarantee, forced thread termination or
hard deadline for a stuck subscriber/filesystem is added. The fixed local proof
bounds are 0.5 seconds for independent responsiveness and 3 seconds for settlement
after a controlled hold is released. Provider-backed execution is separate proof.

## Migration Plan

1. Import `InteractionManager`, `CommitOrchestrator` and `InteractionContext` from
   the application `manager`, `commit` and `context` modules, respectively.
2. Import stream types from `orket.core.contracts.interaction_stream` and packet1
   builders from `orket.core.contracts.interaction_context`. Adapter observation
   clocks live in `orket.streaming.clocks`.
3. Supply absolute roots and explicit enablement. Use `manager.queries` for session
   inspection and `manager.streams.subscribe` for owned transport subscriptions.
   The old manager `subscribe` and unused `mark_tool_result` exports are retired.
4. API integrations use application `InteractionCommands`; the router no longer
   accepts workload policy/commit-factory callbacks. Consume the committed handle
   vocabulary and handle explicit refusal while managed work is still running.
5. Drain the application lifetime before closing its manager. Closed sessions no
   longer remain in the API registry. Preserve existing artifacts; no automatic
   migration, replay or retry of historical interrupted work is performed.

## Rollback Plan

Drain invocations, workloads, subscriptions and file workers before replacing
owners and callers together. Retain all commit/trace/lock files and failed proof.
Do not restore premature pending receipts or stranded admission behavior. Rollback
requires a new version and the same cancellation and real-transport acceptance.

## Versioning Decision

Patch checkpoint with breaking embedding imports and finalize response vocabulary;
explicit migration required. Endpoint paths and packet1/commit artifact schemas
remain stable. Source and installed acceptance must agree before this checkpoint
is declared verified; the full C/D/E/CAP goal remains open.
