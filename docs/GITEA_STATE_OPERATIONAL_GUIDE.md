# Gitea State Operational Guide

Last updated: 2026-02-15.

## Scope
This guide covers operational behavior for the gitea-backed state loop used by Orket workers.

## Lease Semantics
1. Card claims are lease-based and use optimistic concurrency (`ETag`/CAS).
2. A lease contains owner identity, expiry timestamp, and epoch.
3. Same-owner duplicate claim during active lease is idempotent.
4. Different-owner claim is rejected while lease is active.
5. Expired leases are reclaimable, with epoch incremented on successful takeover.

## Duplicate Pickup Tolerance
1. Workers must tolerate races where two runners observe `ready` at nearly the same time.
2. Only one runner should win lease acquire; losers treat the card as unavailable and continue.
3. Transition and event writes are idempotent so duplicate attempts do not corrupt state.
4. Comments are append-only history; repeated event submissions should use idempotency keys.

## Recovery Expectations
1. If worker process dies, lease expiry enables another worker to resume progress.
2. If transition/write hits stale ETag, worker retries with fresh snapshot state.
3. For transient transport failures (timeout/network/rate-limit), adapter retries with bounded backoff.
4. On persistent failure, worker marks terminal state via `release_or_fail` and emits error context.

## Runtime Loop Guardrails
1. Bound execution with:
   - `max_iterations`
   - `max_idle_streak`
   - `max_duration_seconds`
2. Persist run summary artifacts for each coordinator run.
3. Keep readiness gates green before enabling gitea mode in production.
