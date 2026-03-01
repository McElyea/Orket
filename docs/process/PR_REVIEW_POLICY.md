# PR Review Policy

Last reviewed: 2026-02-27

## Policy
1. Required reviewer role: `integrity_guard`.
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
1. Handler: `orket/adapters/vcs/gitea_webhook_handler.py`
2. Persistence: `orket/adapters/vcs/webhook_db.py`
3. Server: `orket/webhook_server.py`

## Approval Behavior
When required review is approved:
1. PR may be merged by automation flow.
2. Follow-on deployment/sandbox behavior depends on enabled runtime policies.
3. Events are logged into webhook DB tables for audit.

## Configuration
Environment:
```bash
GITEA_WEBHOOK_SECRET=<secret>
GITEA_URL=http://localhost:3000
```

Organizational policy fields can be represented in JSON config as needed, but runtime behavior is enforced by webhook handler policy and cycle tracking.
