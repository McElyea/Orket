# PR Review Policy

Last reviewed: 2026-09-18

## Policy
1. Organizational reviewer target: `integrity_guard`. Current signed ingress trusts the supplied reviewer; it does not independently enforce that role.
2. Maximum review cycles per PR: `4`.
3. Escalation on cycle `3` to `lead_architect`.
4. Auto-reject on cycle `4` with follow-up requirements issue.

## Review Cycle Flow
1. PR opened.
2. `integrity_guard` reviews.
3. If changes requested, PR returns to author.
4. Third failed cycle triggers escalation review.
5. Fourth failed cycle closes PR and records failure context.

## Webhook Integration
1. Webhook endpoint: `POST /webhook/gitea`.
2. Default receiver URL: `http://localhost:8080/webhook/gitea`.
3. Signature header required: `X-Gitea-Signature`.
4. Secret source: `GITEA_WEBHOOK_SECRET`.

Implementation locations:
1. Handler: `orket/application/services/gitea_webhook_runtime.py`
2. Persistence: `orket/adapters/vcs/webhook_db.py`
3. Server: `orket/webhook_server.py`

## Approval Behavior
When required review is approved:
1. PR may be merged by automation flow.
2. Merge-time sandbox deployment is intentionally skipped in the current system because Orket is not yet positioned to produce deployable code projects from this webhook path.
3. Review cycles, failure reasons and admitted delivery IDs are persisted in SQLite. Event logs do not establish atomic completion of remote operations.

## Configuration
Environment:
```bash
GITEA_WEBHOOK_SECRET=<secret>
GITEA_URL=https://localhost:3000
```

Organizational policy fields can be represented in JSON config as needed, but runtime behavior is enforced by webhook handler policy and cycle tracking.

Run the explicit factory lifespan. Native signatures, review vocabulary, development HTTP override, delivery dedupe and shutdown limits are specified in `docs/specs/WEBHOOK_RUNTIME_LIFECYCLE.md`.
