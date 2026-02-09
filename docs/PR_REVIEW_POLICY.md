# PR Review Policy (Phase 3)

## Policy: Single Reviewer with Loop Prevention

**Reviewer**: `integrity_guard` (single required approval)

**Max Review Cycles**: 4

**Escalation**: After 3 rejections, escalate to `lead_architect`

**Auto-Reject**: After 4 rejections, auto-close PR and create Requirements Issue

---

## Review Cycle Flow

```
PR Created
  ↓
Cycle 1: integrity_guard reviews
  ↓ (Changes Requested)
Cycle 2: Developer fixes, re-request review
  ↓ (Changes Requested)
Cycle 3: Developer fixes, re-request review
  ↓ (Changes Requested)
🚨 ESCALATION: lead_architect reviews APPROACH
  ↓
Cycle 4: Developer fixes with architect guidance
  ↓ (Changes Requested)
❌ AUTO-REJECT: Close PR, create Requirements Issue
```

---

## Webhook Integration

### Setup Webhook in Gitea

1. Go to repo → **Settings** → **Webhooks**
2. **Add Webhook** → **Gitea**
3. **Target URL**: `http://localhost:5000/webhook/gitea`
4. **Secret**: (from .env: `GITEA_WEBHOOK_SECRET`)
5. **Trigger Events**:
   - ✅ Pull Request Review
   - ✅ Pull Request (merge)
6. **Active**: ✅

### Webhook Handler

Located at: `orket/services/gitea_webhook_handler.py`

Handles:
- PR review events (approved, changes_requested)
- Review cycle tracking
- Architect escalation (cycle 3)
- Auto-reject (cycle 4+)
- Auto-merge on approval
- Sandbox deployment trigger

---

## Auto-Merge on Approval

When `integrity_guard` approves:
1. PR is auto-merged to main
2. Branch is deleted
3. Sandbox deployment triggered

---

## Auto-Reject After 4 Cycles

When PR is rejected 4 times:
1. PR is closed
2. Comment added: "Auto-rejected after 4 cycles"
3. Requirements Issue created with:
   - All rejection reasons
   - Architect guidance (if provided)
   - Root cause analysis checklist
   - Next steps

---

## Architect Escalation (Cycle 3)

When PR is rejected 3 times:
1. Comment added requesting architect review
2. Architect reviews **APPROACH**, not implementation
3. Architect provides:
   - Architectural guidance
   - Alternative approaches
   - Specific suggestions for moving forward

---

## Configuration

Add to `.env`:
```bash
GITEA_WEBHOOK_SECRET=your-webhook-secret-here
```

Add to `config/organization.json`:
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

---

## Testing

### Manual Test

1. Create test PR in Gitea
2. Request changes 3 times (as integrity_guard)
3. Verify architect escalation comment
4. Request changes 1 more time
5. Verify PR auto-closes
6. Verify Requirements Issue created

### API Test

```python
from orket.services.gitea_webhook_handler import GiteaWebhookHandler

handler = GiteaWebhookHandler()

# Simulate review webhook
payload = {
    "action": "submitted",
    "review": {
        "state": "changes_requested",
        "user": {"login": "integrity_guard"},
        "body": "Needs refactoring"
    },
    "pull_request": {"number": 1},
    "repository": {
        "owner": {"login": "Orket"},
        "name": "test-project"
    }
}

await handler.handle_webhook("pull_request_review", payload)
```

---

## Future: Two-Role Review (v0.4.0)

When ready to upgrade:
1. Change `required_approvals: 2`
2. Add `required_reviewers: ["technical", "integrity_guard"]`
3. Implement role-based review assignment
4. Update escalation logic for multi-reviewer scenarios
