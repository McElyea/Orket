# Exporter and builtin HTTP request ownership

## Summary

- Owner: Codex for Orket Core
- Date: 2026-09-22
- Contract: `docs/specs/SHORT_HTTP_REQUEST_OWNERSHIP.md`
- Scope: canonical D2/D3 after published v0.6.94.

## Delta

The same 16 controls on source and byte-verified installed v0.6.94 produce
15 failures and one healthy routing control: three exporter requests use ambient
proxy settings instead of captured settings, three controlled native trust holds
block the event loop and exceed the existing 0.5-second SQLite bound, and nine
interrupted requests abandon actual connection-pool cleanup. Two earlier cleanup
diagnostics targeted methods bypassed by HTTPX context-manager exit; those missed
barriers are retained and are not cleanup counterexamples. A further actual POST
control reproduces a changed reported argument hash after caller mutation on source
and the published wheel. Freeze invocation arguments before dispatch so the event
identity remains aligned with the sent body. Final installed control: 17 cases,
16 failures and one healthy routing control.

Application composition supplies a short-request port using existing captured
network, native construction and lifetime authorities. Exporter binding and HTTP
policy share captured construction inputs. Builtin HTTP captures ambient inputs
per request, preserving operator changes between requests. Requests snapshot
borrowed nested values before native dispatch. Preserve allowlist/effect identity,
authentication, response/error semantics, export intent/recovery and deadlines.

## Migration Plan

1. No compatibility shim. Raw exporter and builtin executor embeddings supply
   `HttpRequestPort`; normal application composition supplies it automatically.
2. Use `create_gitea_artifact_exporter` in native composition; async embeddings
   retain that factory through the existing owned native worker.
3. Require the identical red source/installed controls, actual partial-acquisition
   and interruption proof, preserved BT source/installed matrix, disposable Gitea
   export/recovery and teardown, package parity and canonical structural gates.

## Rollback Plan

1. Failed preservation or acceptance blocks publication. Repair or revert the
   scoped implementation, caller migration and authority together.
2. No storage migration. Observe remote effects and retained export state before
   retrying; client cleanup does not roll back a committed effect.
3. Preserve failed diagnostics and the prior published checkpoint.

## Versioning Decision

- Patch checkpoint: 0.6.95, effective after scoped verification.
- `compatibility_status`: `breaking`
- `affected_audience`: `all`
- `migration_requirement`: `required`
- No whole-plan completion, release readiness or lane retirement is inferred.
