# Gitea HTTP inputs and owned construction

Owner: Codex for Orket Core
Date: 2026-09-22
Status: Scoped implementation contract; acceptance remains in the canonical plan

The published v0.6.92 wheel routes six supplied/empty-environment state/webhook
cases through the ambient proxy. Two ambient-default controls pass. Identical
actual TCP controls reproduce six failures on source and byte-verified installed
v0.6.92. Fixture responses establish routing, not actual Gitea or model acceptance.

Patch 0.6.93 reuses the existing HTTP policy, native TLS builder and resource owner.
Application composition binds an explicit client ownership port. Native entry
refusal requires async callers to adopt owned construction. Both Gitea CLI paths
close adapters through the existing runtime owner, including partial composition
failure. Native construction error/cleanup supervision is shared with the provider
factory; no new cancellation loop or compatibility shim is introduced.

Compatibility: breaking for direct raw adapter constructors and event-loop native
embeddings. Migrate state callers to `create_gitea_state_adapter_async`, or hold the
native factory inside `open_runtime_owner`. Native embeddings supply explicit HTTP
ownership. Webhook async composition uses `build_webhook_runtime`.
Preserve authorization, retry/error handling, URL refusal, BT1-5, admitted webhook
work, existing assertions and deadlines. Scope authority:
`docs/specs/GITEA_HTTP_CLIENT_OWNERSHIP.md`.

Acceptance requires source and installed Windows3.11/3.12 with identical retained
cases, complete package parity, actual TLS/proxy/credential effects, native and
request interruption, partial acquisition/cleanup failures and responsive independent
SQLite work. Retain all failed probes and the Linux clock blocker. Fresh disposable
Gitea proof must verify teardown. Shared provider changes require renewed actual
transport observation without treating returned text as successful model instruction.
Failure blocks this scoped checkpoint; repair or revert code and authority together.
No main merge, full-plan completion, release readiness or retirement follows.

The async webhook builder snapshots a supplied configuration mapping before its
first await, so storage roots and HTTP policy observe the same input even when
the caller later mutates its original mapping. Retain the actual split-input
counterexample and require fresh frozen acceptance after this correction.
