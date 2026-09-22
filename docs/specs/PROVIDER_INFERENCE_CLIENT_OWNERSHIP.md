# Provider inference client inputs and ownership

Last updated: 2026-09-22
Status: Implementation contract; acceptance remains in the architectural-truth plan

Application composition owns provider client construction and cleanup. Native
construction refuses event-loop entry before effects. The provider's async factory captures
one environment and absolute lexical directory before dispatch, retains the native
worker, and closes any completed provider that interruption prevents transferring
to its caller. Failed construction closes every resource acquired before failure.

Inference clients reuse the catalog proxy, certificate, host TLS-default and key-log
policy from `PROVIDER_HTTP_CATALOG_INPUTS.md`. Relative trust/key-log paths use the
captured directory; no file-content snapshot is implied. Explicit empty environment
does not inherit ambient proxy or credential policy. ModelClientFactory retains its
environment and lexical directory at factory construction.

Ollama request authentication explicitly overrides the SDK's ambient default header
using HTTPX's public authentication interface. A captured OLLAMA_API_KEY supplies
the request credential; absence removes the SDK's seeded Authorization header.
This controls outbound authentication, not the purity of SDK internal environment
reads or its platform/version User-Agent. Do not copy SDK internals, mutate global
environment, weaken TLS verification or add another proxy/certificate authority.

Preserve backend-specific behavior: OpenAI-compatible connection/read/write/pool
budgets and disabled redirects; Ollama SDK redirects and its outer finite generation
deadline; retry policy, API keys, pinned-target admission, prompt handling, response
validation and provider lineage. Non-finite model budgets must fail before native
or network effects. Catalog budgets and behavior remain unchanged.

Each provider owns its native client and acquired transports. Replacing its public
client transfers the replacement to provider cleanup too; the originally acquired
resources remain owned. Cleanup is retained through repeated cancellation and
failures remain visible. A failed or interrupted close is not normal completion.
Caller-provided factories remain responsible for partial resources they do not
return or explicitly register; application ownership retains their returned client.

Use the native factory only before an event loop or inside an owned worker. Async
callers use owned async composition; SDK synchronous construction/generation/close
run inside drained native workers. Constructor fixtures must bind the supplied
owner even when they intentionally create no HTTP resources. Raw adapters require the explicit application
HTTP ownership port. This contract does not establish model inference from fixture
responses, daemon rollback, hostile-code containment, atomic provider configuration,
or complete D/E/CAP. Actual provider availability and CAP acceptance remain separate.

SDK workload parents issue the authorization envelope and validate configured
capability identifiers before dispatch. Their request context has no live providers.
Only the native subprocess materializes its execution registry; its resource scope
registers each newly created default model provider immediately, before subsequent
registry/context construction or child authorization checks. It closes that provider
before publishing the result, including construction, authorization and workload
failures. Cleanup failure publishes failure with the prior workload result and
capability report retained. Configured borrowed providers are not acquired by this
scope. Native callers that build a raw registry without supplying an ownership
callback own the returned default provider themselves.

Forced subprocess termination is governed by the existing owned-command supervisor:
process-tree cleanup does not establish graceful Python client cleanup or termination
of remote inference. This change does not widen that claim.

Card preparation owns primary and ODR-auditor close operations to completion before
reporting caller cancellation. Physical HTTP closure alone must not leave a provider's
successful close result unadopted. Reuse the existing owned-operation mechanism;
preserve close failures and do not mark an interrupted provider close successful.
