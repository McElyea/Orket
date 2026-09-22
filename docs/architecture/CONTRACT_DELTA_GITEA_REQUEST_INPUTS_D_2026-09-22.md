# Gitea retry values and lease body-limit inputs

## Summary

- Owner: Codex for Orket Core
- Date: 2026-09-22
- Contract: `docs/specs/GITEA_HTTP_CLIENT_OWNERSHIP.md`
- Scope: canonical D2 after published v0.6.93; broader D/E/CAP remains open.

## Delta

The identical 24 actual TCP controls on source and byte-verified installed v0.6.93
produce 18 failures and six passing controls. Mutating borrowed nested body, query
and header values changes a later retry. Lease acquire/renew reads ambient body
limits even when construction captured an explicit or empty environment.

Snapshot borrowed request values once before the retry loop. Compile the existing
body-limit rule from captured environment in application composition; pass the
integer to the adapter and lease manager. Preserve the default, invalid-value
fallback, one-byte minimum, UTF-8 byte counting, conditional PATCH, lease/version
transitions, per-attempt authentication, retry classification, backoff and deadlines.
No hidden ambient lookup or compatibility forwarding path remains in lease encoding.

## Migration Plan

1. No compatibility window for ambient lease-limit observation. Existing application
   factories supply the captured value. Raw native adapter callers additionally
   provide `issue_body_max_bytes`; reconstruct an adapter to change its policy.
2. Callers retain ownership of request dictionaries; later mutation applies to later
   operations, not retries already admitted. Accepted JSON/query/header shapes stay
   supported; this change does not add another request serialization format.
3. Require the red source/installed controls, fresh preserved BT/Gitea source and
   Windows installed cases, real disposable Gitea teardown, package parity,
   dependency policy, and unchanged latency/deadline checks before checkpointing.

## Rollback Plan

1. Failed preservation or acceptance blocks publication; repair or revert the scoped
   code, caller migration and authority together.
2. No durable storage schema changes. Observe actual remote lease/version state
   before retrying an interrupted operation; client cleanup is not remote rollback.
3. Preserve all failed probes and the prior published checkpoint.

## Versioning Decision

- Patch checkpoint: 0.6.94, effective 2026-09-22 after scoped verification.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- Direct raw embeddings must supply the lease limit. No full-plan completion,
  Linux clock repair, release readiness, main merge or lane retirement is inferred.
