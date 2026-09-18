# Standalone Gitea webhook runtime

Last updated: 2026-09-18
Status: Active contract; 0.6.20 migration

The admitted factory is `orket.interfaces.runtime_entrypoints.create_webhook_app`
with `CompositionConfig`. It retains module-profile authorization and passes the
selected project root to the transport factory. Standalone startup is
`python -m orket.webhook_server` or
`python -m uvicorn orket.webhook_server:create_webhook_app --factory`.
There is no module-default `app` or handler proxy. Embedded callers retain the
returned app and run its lifespan once; reuse, including overlapping startup,
requires a new app.

## Captured inputs and storage

Factory invocation captures the project and invocation roots, Gitea endpoint and
credentials, webhook secret, test-endpoint authentication, rate limit and worker
hint. The low-level transport factory also accepts an explicit environment mapping
and runtime inputs. Later changes to that mapping, process environment or CWD do
not reconfigure the existing ingress. Rotation requires a new application.

The webhook database remains project-relative at
`.orket/durable/db/webhook.db`. Review engines retain the captured invocation's
runtime database and durable-root selection; project roots alone do not isolate
those stores. The runtime-path adapter owns existing legacy filename migration
using the captured invocation root. Sandbox lifecycle storage likewise retains
that root. This does not make all downstream engine/provider/settings inputs
immutable; remaining settings ownership belongs to architectural-truth D.

HTTPS is required for outbound Gitea credentials. Explicit local development
`ORKET_GITEA_ALLOW_INSECURE=true` admits HTTP and reports degraded transport.
Embedded credentials, URL query/fragment and missing host are refused. Default
startup requires `GITEA_WEBHOOK_SECRET` and `GITEA_ADMIN_PASSWORD`.

## Ingress and review policy

Authenticate raw request bytes with HMAC-SHA256 before payload interpretation.
Native `X-Gitea-Signature` is the bare lowercase hexadecimal digest; the previously
admitted `sha256=` form remains accepted. Missing or incorrect signatures refuse
with 401. Bodies over 1 MiB refuse with 413. The optional test endpoint remains
disabled by default and uses captured test-token authentication before API-key
authentication when both are configured.

Gitea 1.25.4 review events use `pull_request_approved`, `pull_request_rejected`
or `pull_request_comment`, with `action=reviewed`, `sender`, and
`review.type` set to `pull_request_review_approved`, `pull_request_review_rejected`
or `pull_request_review_comment`, plus `review.content`.
The VCS adapter translates these to existing approved/changes-requested/commented
review values. The normalized `pull_request_review` event and previously admitted
review user/state/body shape remain supported. Native mixed vocabulary, missing
sender and conflicting event/review types return structured validation errors.
Review thresholds remain escalation on cycle 3 and rejection on cycle 4.
The signed sender is trusted; ingress does not independently authorize a reviewer
role. Merge-time sandbox deployment remains explicitly unsupported and skipped.

`X-Gitea-Delivery` reaches the review dedupe store. Conflicting header/body
identifiers refuse before dispatch; legacy payload identifiers survive validation.
A duplicate response means that ID was previously admitted, not that its remote
effects completed. HMAC covers the body, not delivery headers. This is neither a
freshness/anti-replay guarantee nor an atomic SQLite/Gitea transaction. Distinct
delivery IDs can describe the same review. Failed or interrupted remote operations
require inspection; automatic redispatch is not authorized by a duplicate result.

Rate admission uses an injected monotonic clock and a separate limiter per app
per process. Nonfinite or backward clock observations refuse admission. Health
reports `rate_limit_scope=per_application_per_process`; a worker-count hint does
not configure workers or a shared limiter.

## Ownership and failure

The lifespan constructs application dependencies in an owned worker. Cancellation
drains construction and closes any completed owner. ASGI middleware admits every
request through `ApplicationRuntimeLifetime`. Shutdown refuses new work with 503,
waits for admitted request cleanup, drains review tasks, then closes resources and
the HTTP client. An engine remains parent-owned until its review task starts.
Repeated cancellation of shutdown waiters does not release that ownership.

Unexpected background or cleanup failures remain observable to every close caller
and prevent `closed=True`; failed background work also stops new admission.
An expected unsuccessful typed review result is logged as such. Review-triggered
responses are admission acknowledgments, not provider completion claims. There is
no forced thread termination, shutdown deadline, remote rollback or hostile-code
containment guarantee.

Direct embeddings import `GiteaWebhookHandler` or the async
`build_webhook_runtime` from `orket.application.services.gitea_webhook_runtime`.
Use the async builder on async paths; synchronous construction belongs off the
event loop. The owner must be closed. Previous adapter handler/payload imports
are retired without forwarding modules.
