# Webhook application authority and owned lifetime

Owner: Orket Core
Date: 2026-09-18
Status: implemented with focused source/installed proof; whole-lane acceptance remains open

## Summary and delta

Before 0.6.20, the standalone Gitea webhook factory returned one global application.
Request-time environment reads change authentication on existing applications,
transport validation loses delivery identifiers, and adapter-owned PR review
tasks outlive handler close. Installed 0.6.19 reproduces these defects under
`.tmp/c-dependency-frontier/webhook-before/` and
`webhook-lifetime-bootstrapped/`. The existing 73-case source selection passes;
those passes do not establish the missing ownership guarantees.

Move review/lifecycle policy and engine construction into application services.
Retain HTTP and SQLite integration effects in adapters. Each factory result owns
its captured project/security/rate-limit inputs, handler, admitted requests and
review tasks. Reuse the API's task-lifetime implementation through a shared
application owner; preserve its existing request cancellation and cleanup rules.
No forwarding proxy or application-to-interface import is admitted.

Retain delivery identity through authenticated public ingress before review
deduplication. Preserve existing review thresholds, payload validation, explicit plaintext-development admission and unsupported
sandbox outcome. Correct the former HMAC claim: native Gitea uses a bare digest;
the existing prefixed form remains admitted. Translate actual 1.25.4 review
events and typed payloads through the VCS adapter. Mixed or conflicting values
refuse before policy effects.
Receiving a duplicate is not proof that the original remote operation completed.
This does not introduce an atomic SQLite/Gitea transaction, remote rollback,
cross-worker rate limiting, provider completion or hostile-code containment.

## Migration plan

1. Patch checkpoint: 0.6.20. Remove module-default webhook app/handler
   ownership. Call `create_webhook_app(...)`, retain its returned app and run its
   lifespan. Startup must use that instance or the explicit factory form.
2. Direct handler embeddings migrate from the adapter namespace to application
   composition, retain their owner and close it. Construct blocking dependencies
   through owned workers; do not initialize them on a request's event loop.
3. Existing applications retain captured authentication and roots. Rotation or
   reconfiguration requires a new application. Declare per-application/per-process
   rate-limit scope truthfully; independent apps do not share an in-memory limiter.
4. Update concrete callers, active authorities and Quality in the same change.
   Prove real HTTP/SQLite ingress, duplicate delivery, independent apps, failed
   initialization, active review/request cancellation and retained close failures.
   Preserve API lifetime regressions and verify fresh installed execution.
5. Distinguish actual disposable Gitea proof from controlled HTTP responses and
   held-review tests. Provider and final full-plan gates remain separate obligations.

## Rollback plan

Revert application ownership, transport and callers together if the declared
admission or lifetime guarantees regress. Retain database history and original
evidence; do not automatically replay uncertain remote effects. Reverting restores
the demonstrated global-state and unowned-task defects, not conformance.

## Versioning decision and current proof

Patch checkpoint 0.6.20; breaking embedding migration is recorded in the changelog.
The durable contract is `docs/specs/WEBHOOK_RUNTIME_LIFECYCLE.md`.

Official Gitea documentation describes the native signature:
[webhook delivery headers](https://docs.gitea.com/usage/repository/webhooks/).
The retained actual Gitea 1.25.4 review delivery is more specific than generic
documentation examples: `pull_request_rejected` and
`review.type=pull_request_review_rejected` were previously ignored. Acceptance
uses actual wire observations. Initial fixture failures (wrong hook subscription,
wrong approval token and an undrained capture queue) remain retained separately
from that product counterexample. Final focused source/installed acceptance and retained candidate regressions
are recorded in the canonical architectural-truth plan; full-plan gates remain open.
