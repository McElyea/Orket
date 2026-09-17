# Governed-agent terminal transactions

## Summary

- Owner: Orket Core, architectural-truth BT-5.3-5.
- Date: 2026-09-14.
- Contracts: `docs/specs/GOVERNED_AGENT_LOOP_V1.md`, `docs/specs/API_RUNTIME_LIFECYCLE.md`.
- Status: scoped terminal/cancellation repair accepted on the current source and four installed environments; historical-state and wider family conformance remain open.

## Delta

The bounded loop previously committed final truth before updating its attempt and
run. Failure at the attempt write left shared success on an unfinished run.
`governed_agent_terminal_service.close_agent_run` now receives the existing
`ControlPlaneTransactionFactory` and commits all three records together. It
compares retained run/attempt state and refuses pre-existing conflicting truth.
Wake guard failure before the transaction returns also rolls back publication.

Loop construction explicitly receives the shared transaction owner. Runtime
composition rejects differently configured execution/iteration/record stores.
Terminal reads use the same transaction owner; inspection/operator typing reuses
the existing core record contract. Bounded-loop final truth now uses the shared
publication validator. Operator stop resolves the accepted decision's action
references against actual retained run/invocation-bound commands.

Effect denial uses that transaction for approval CAS, its bound operator actions,
reservation release, checkpoint rejection and terminal truth/attempt/run. The
pending-gate implementation moves from the oversized `async_repositories.py` into
`async_pending_gate_repository.py`; all consumers import its single implementation
and the shared core port replaces duplicated application protocols. Its borrowed
connection never commits the caller's transaction or initializes outside it.

Operator cancellation retains intent before child teardown, then compares
run/attempt state and commits terminal records together. A failed terminal write
can be retried; a cancelled invocation remains an observation obligation, so a
separate CLI cannot claim a formerly unknown child has stopped. Result vocabulary
and continuation policy are unchanged. No compatibility shim or second
final-truth store is introduced.

The installed family gate also exposed API shutdown waiting on a still-running
supervisor without a pending cancellation. A task's cancellation count is not
proof that the API owner requested it: an internal timeout can consume its own
request. The container now records its cancellation requests separately and
shares that record between disconnect and teardown. Each owner cancellation is
issued once, preserving cleanup when those paths overlap.

## Migration and limits

No stored schemas, identifiers or receipt formats change. Preserve old execution,
iteration and terminal evidence. New terminal publication refuses conflicting
retained state; this change does not reconcile a previously split publication.
Historical inspection/reentry consistency remains a separate BT-5 obligation.
Iteration evidence and cancellation intent lie outside the terminal transaction.
Earlier split histories still require explicit BT-5 disposition before reentry.

## Proof and rollback

The common composed-path test covers cards, outward and governed-agent runs with
successful execution and failures at terminal attempt/run writes. The original
governed-agent counterexample and copied database remain retained in
`.tmp/bt5-family-conformance/`. Source regression is recorded in the canonical plan.
The denial/cancellation controls retain four original terminal-write failures;
the retry controls additionally expose loss of unknown-child uncertainty after
interrupted cancellation publication. Local proof uses real SQLite and native
child cancellation with controlled inference. Installed/native interruption and
actual-provider proof pass their declared envelope: eight installed llama.cpp
cases and four native terminal-death/retry cases on each owned host/interpreter.
The 642-case source and three installed envelopes pass. The Windows 3.12 full
regression stalled at API shutdown. Its captured coroutine state and manual rescue
remain retained; that instrumented run cannot establish candidate acceptance.
Three deterministic internal-timeout races failed before the cancellation repair;
all 22 focused ownership cases now pass with it. The first attempted repair
interrupted existing cleanup and its three failures remain retained. The fresh
wheel `7558b9c7…794539` passes 664 matching source and installed cases on
Windows/Linux Python 3.11/3.12, eight installed llama.cpp cases, and four native
interruption/retry cases per installed environment. The final test-only polling
repair passes its three cases in source and all four installed environments
without changing the frozen regression inputs. Exact hashes, source delta and
retained evidence are bound by
`.tmp/bt5-family-conformance/gate-after-shutdown/audit.json`.

Stop admission if the transaction regresses; preserve evidence and do not return
to an old writer against a live store to bypass the new conflict checks.
This is an uncommitted core 0.6.2 candidate change, not a release or tag.
