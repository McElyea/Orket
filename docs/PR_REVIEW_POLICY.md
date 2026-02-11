# PR Review Policy

## Policy
- Required reviewer: `integrity_guard`
- Maximum review cycles: 4
- Escalation threshold: 3 rejected cycles
- Auto-reject threshold: 4 rejected cycles

## Review Flow
1. PR created.
2. `integrity_guard` reviews.
3. If changes requested, developer updates and re-requests review.
4. On third rejection, escalate approach review to `lead_architect`.
5. On fourth rejection, close PR and open a requirements issue.

## Webhook Integration
Configure Gitea webhook:
1. Repository Settings -> Webhooks -> Add Gitea webhook.
2. Target URL: `http://localhost:5000/webhook/gitea`
3. Secret: `.env` value `GITEA_WEBHOOK_SECRET`
4. Trigger events: pull request review and pull request updates.

Handler location: `orket/services/gitea_webhook_handler.py`

## Approval Behavior
When required review approves:
1. PR is merged.
2. Branch is deleted.
3. Deployment hook is triggered if enabled.

## Configuration
`.env`:
```bash
GITEA_WEBHOOK_SECRET=your-webhook-secret
```

`config/organization.json`:
```json
{
  "pr_review_policy": {
    "max_review_cycles": 4,
    "escalation_cycle": 3,
    "required_approvals": 1,
    "required_reviewer": "integrity_guard",
    "auto_merge": true,
    "auto_deploy": true
  }
}
```
