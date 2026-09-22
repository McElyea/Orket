# Gitea HTTP input and construction ownership

Owner: Orket Core
Last updated: 2026-09-22
Status: Active scoped contract; broader architectural acceptance remains open

Gitea state and webhook clients use the captured network policy defined by
`PROVIDER_HTTP_CATALOG_INPUTS.md`: explicit environment and lexical invocation
root, verified trust, proxy routing and optional key logging. An empty mapping
has no ambient or registry fallback. Unsupported policy fails explicitly.
The common native HTTP builder and acquired-resource owner are authoritative;
Gitea does not maintain another proxy compiler or cancellation loop.

Application composition supplies `CapturedHttpClientPort`. Native state callers
use `create_gitea_state_adapter`; async callers use its async variant or retain
the native factory through `open_runtime_owner`. Raw state adapters require the
port. Native adapter/factory and webhook construction refuse event-loop entry
before effects. `build_webhook_runtime` captures network inputs before dispatch
and uses the existing runtime owner to close completed but unadopted handlers.
The synchronous webhook embedding owns its handler through close.

Construction owns every acquired HTTP transport/client, including partial native
failure and replacement clients handed to close. Construction and cleanup failure
remain observable together. Repeated caller cancellation cannot abandon acquired
resources. The existing webhook application lifetime still governs admitted work,
background tasks and failure envelopes; teardown failure retains its cause.
Borrowed sandbox orchestrator ownership remains unchanged.

State authentication, lazy token headers, retry/error classification and domain
transitions remain unchanged. Webhook Basic authentication, URL admission and
explicit local HTTP allowance remain unchanged. Both client families disable
redirects. State scalar timeout defaults to 20 seconds; webhook timeout remains
10 seconds. Non-finite state budgets refuse before TLS or HTTP acquisition.
No timeout or test deadline is extended to obtain acceptance.

The state coordinator and reconciliation CLI paths capture environment, cwd and
argument values before awaiting construction and retain the adapter through the
whole body, including later composition failure. Reconciliation remains read-only
and halt-and-alert. Coordinator mutation still requires `--allow-mutate`.
Coordinator output keeps its canonical path and now uses the shared diff ledger:
`benchmarks/results/gitea/gitea_state_worker_run_summary.json`. Reconciliation
keeps `benchmarks/results/gitea/state_reconciliation.json`.

Controlled TCP/TLS, SQLite and native filesystem observations establish scoped
transport, input and lifetime behavior. Actual disposable Gitea proof is separate
and must verify container/listener/client teardown. Neither proves model correctness,
CAP acceptance, remote-effect rollback or a stuck-thread termination bound.
Trust-directory contents remain live and OpenSSL can load them during handshake.
HTTP artifact export and builtin connector ownership follow
`SHORT_HTTP_REQUEST_OWNERSHIP.md`. Wider D2/D3/D4 effect coverage remains open. Linux clock, full coverage, hosted
Quality and E/CAP acceptance are not inferred from this contract.

The async webhook builder snapshots a supplied configuration mapping before its
first await, so storage roots and HTTP policy observe the same input even when
the caller later mutates its original mapping. Retain the actual split-input
counterexample and require fresh frozen acceptance after this correction.

Request-interruption controls require actual peer termination (EOF or an allowed
connection reset) and completed server/client cleanup. They do not send a
successful response after the client disconnects.
The shared observation server bounds its own close at five seconds. Preserve the
failed Python 3.12.2 candidate and callback diagnostic: Windows socket shutdown
raised ConnectionResetError before asyncio detached the server connection.
An earlier source or Python 3.11 pass does not establish that candidate's acceptance.

Each state retry operation snapshots its borrowed payload, query values and extra
headers before the first request. Nested JSON values and accepted query sequences
remain the same across attempts. Per-attempt authorization, retry classes, attempt
limits and backoff deadlines retain their existing behavior.

Application construction compiles `ORKET_GITEA_ISSUE_BODY_MAX_BYTES` from the same
captured environment used by the HTTP owner. Missing or malformed values retain
the 65,000-byte default; parsed values retain the existing minimum of one byte.
Lease acquisition and renewal consume that explicit integer for UTF-8 body
admission before PATCH. An empty environment uses the default; omitted environment
captures ambient values at construction. Later mapping or environment changes do
not reconfigure an existing adapter. Raw native adapters require an explicit
`issue_body_max_bytes` value. This does not extend the size rule to other writes.
Migration and acceptance: `docs/architecture/CONTRACT_DELTA_GITEA_REQUEST_INPUTS_D_2026-09-22.md`.
