# OpenClaw interactive exchange ownership

Owner: Codex for Orket Core
Date: 2026-09-22
Status: Scoped implementation contract; acceptance recorded in canonical plan
Contract: [OpenClaw process ownership](../specs/OPENCLAW_PROCESS_OWNERSHIP.md)
Acceptance: [Architectural-truth plan](../projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md)

## Delta

Previously the adapter spawned a direct child, drained stderr only after exit and
killed/waited only that leader. Request writes and pipe closure could block without
a finite deadline. Cancellation or leader exit did not establish descendant cleanup.

The application supplies the existing OS command owner. Add sequential JSONL exchange
to that owner's native transport, retaining one tree lifetime and its output bounds.
Capture invocation inputs before dispatch. Preserve accepted response prefixes and
refuse incomplete capture or uncertain cleanup. Do not convert the interaction into
an all-input batch or treat process cleanup as external-effect rollback.

## Migration and validation

The 0.6.89 pre-1.0 patch checkpoint has an explicit breaking contract. Adapter
composition supplies the application command runner. Native command APIs keep their
existing batch semantics. There is no compatibility shim. Callers must handle
typed cleanup uncertainty and bounded interactive I/O failure. Validation uses real
subprocess trees, pipes, independent effect observations and source/installed parity;
synthetic result refusals alone cannot establish native cleanup.

The existing lifetime schema admits `protocol_failed` for invalid interactive
responses; it remains a non-success reason. One shared pure decoder enforces the
64 KiB JSON-object response rule in the supervisor and adapter. Request frames are
single-line JSON objects and are validated before process admission. A final valid
EOF-terminated response remains accepted, preserving prior `readline` behavior.

## Rollback

A confirmed regression blocks publication. Revert the scoped implementation,
caller migration and authority records together, then repeat affected proof. Do not
silently restore direct-child fallback. Accepted external effects remain authoritative;
code rollback cannot reverse them. No hostile-code or actual-model acceptance is implied.
