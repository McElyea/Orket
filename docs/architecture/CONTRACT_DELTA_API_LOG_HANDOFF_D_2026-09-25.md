# API log subscription handoff lifetime

## Summary

- Owner: Orket Core, architectural-truth D.
- Date and target: 2026-09-25, unpublished v0.6.106 candidate.
- Contract: `docs/specs/API_RUNTIME_LIFECYCLE.md`.
- The canonical remediation plan owns execution evidence and publication status.

## Delta

API subscriptions previously tested `owner.accepting_work` before scheduling a
loop callback and again before its queue insertion. Closing the application could
therefore remove the subscription and discard an already captured callback.

The existing process logging owner now snapshots open registrations before the
standard handler and file stages. Each snapshot issues one acknowledgement token
per registration. API registrations use `open -> draining -> closed`: draining
atomically excludes later snapshots, retains the subscriber count, and waits for
previously issued tokens before removal. The application closes this registration
through its existing resource lifetime and retained native worker. Repeated caller
cancellation and timeout cannot abandon the drain. Other applications remain open.

An API callback transfers its token to the scheduled loop closure. That closure
acknowledges in `finally` after `event_queue.put_nowait` attempts, including queue
failure. Scheduling failure releases the token in the publication owner and keeps
the existing subscriber-failure diagnostic. Earlier publication failure releases
tokens whose callbacks were never invoked, preserving the original failure.
Acknowledgement is idempotent; no retry or duplicate handoff is introduced.

Legacy `subscribe_to_events` remains callback-idempotent. Its synchronous
unsubscribe excludes future snapshots and removes the count immediately; it is
not a drain and cannot revoke a captured callback. All callbacks use the same
snapshot cutoff, so subscription changes during a handler affect later events.

## Migration Plan

1. API composition registers its handoff resource before starting the broadcaster
   and awaits its asynchronous close through the existing application owner.
2. Internal handoff subscribers must acknowledge a successfully scheduled callback
   after its later handoff attempt. Ordinary callback subscribers need no change.
3. Preserve the one queue, daemon, failure slot and append frontier. No application
   stops or resets the process writer, and no global queue join closes a subscription.

## Rollback Plan

Lost captured callbacks, leaked tokens, premature close, or interference with peer
applications block publication. Correct the shared registration protocol while
retaining failures; do not restore the two admission checks that discard work.

## Versioning Decision

The internal API subscription resource changes to asynchronous drain. API close
may now wait for a captured event-queue handoff that previously disappeared.
Persisted event records and public callback signatures remain unchanged.

## Proof and claim ceiling

The four source opening cases reached premature close and absent queue attempts.
The same 96 cases pass in fresh source and installed Windows Python 3.11/3.12,
including the four opening identities, three failed-stage controls and all 84
extraction guards. Physical JSONL/SQLite, package origins, input identity and
owner settlement pass. The plan retains the separate wrong-interpreter launch
and missing fixture-support collection failures. Full successor acceptance
remains pending. This boundary proves local settlement or an attempted
application queue handoff, never WebSocket delivery or durable event processing.
The broadcaster may already be stopped when the queue attempt occurs. An earlier
publication failure can settle an uninvoked callback without a queue attempt.
No deadline, forced thread termination, retry, second writer, atomic multi-sink
transaction or crash durability is added. Optional logging still needs its
separate event-loop offload, capture and preparation correction.
