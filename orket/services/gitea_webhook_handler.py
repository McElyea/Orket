"""
Gitea Webhook Handler - Phase 3: PR Review Policy Enforcement

Handles webhooks from Gitea for:
1. PR review events (approved, changes_requested)
2. Review cycle tracking (max 4 cycles)
3. Architect escalation (after 3 rejections)
4. Auto-reject (after 4 rejections)
5. Auto-merge on approval
6. Sandbox deployment trigger
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from pathlib import Path
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

from orket.logging import log_event

load_dotenv()


class GiteaWebhookHandler:
    """
    Application Service: Handles Gitea webhook events.
    Enforces PR review policy with loop prevention.
    """

    def __init__(self, gitea_url: str = "http://localhost:3000", workspace: Optional[Path] = None):
        self.gitea_url = gitea_url
        self.gitea_user = os.getenv("GITEA_ADMIN_USER", "Orket")
        self.gitea_password = os.getenv("GITEA_ADMIN_PASSWORD", "")
        self.workspace = workspace or Path.cwd()
        self.auth = (self.gitea_user, self.gitea_password)

        # Review cycle tracking (in-memory for now, should be in DB)
        self.pr_review_cycles: Dict[str, int] = {}  # pr_key -> cycle_count
        self.pr_failure_reasons: Dict[str, list] = {}  # pr_key -> [reasons]

    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Main webhook handler dispatcher.

        Args:
            event_type: Type of webhook (pull_request, pull_request_review, etc.)
            payload: Webhook payload from Gitea

        Returns:
            Response dict with status and message
        """
        if event_type == "pull_request_review":
            return await self._handle_pr_review(payload)
        elif event_type == "pull_request" and payload.get("action") == "closed":
            if payload["pull_request"].get("merged"):
                return await self._handle_pr_merged(payload)

        return {"status": "ignored", "message": f"Event type {event_type} not handled"}

    async def _handle_pr_review(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle pull request review events.

        Enforces review cycle policy:
        - Cycle 1-2: Normal review
        - Cycle 3: Escalate to architect
        - Cycle 4: Last chance
        - After 4: Auto-reject
        """
        pr = payload["pull_request"]
        review = payload["review"]
        repo = payload["repository"]

        pr_number = pr["number"]
        pr_key = f"{repo['owner']['login']}/{repo['name']}/#{pr_number}"
        reviewer = review["user"]["login"]
        review_state = review["state"]  # "approved", "changes_requested", "commented"

        log_event("pr_review", {
            "pr": pr_key,
            "reviewer": reviewer,
            "state": review_state
        }, self.workspace)

        # APPROVED → Auto-merge
        if review_state == "approved":
            await self._auto_merge(repo, pr_number)
            return {"status": "success", "message": f"PR #{pr_number} approved and merged"}

        # CHANGES_REQUESTED → Track cycles
        if review_state == "changes_requested":
            cycles = self.pr_review_cycles.get(pr_key, 0) + 1
            self.pr_review_cycles[pr_key] = cycles

            # Store failure reason
            if pr_key not in self.pr_failure_reasons:
                self.pr_failure_reasons[pr_key] = []
            self.pr_failure_reasons[pr_key].append({
                "cycle": cycles,
                "reviewer": reviewer,
                "reason": review.get("body", "No reason provided"),
                "timestamp": datetime.utcnow().isoformat()
            })

            # Cycle 3: Escalate to architect
            if cycles == 3:
                await self._escalate_to_architect(repo, pr_number)
                return {"status": "escalated", "message": f"PR #{pr_number} escalated to architect"}

            # Cycle 4+: Auto-reject
            elif cycles >= 4:
                await self._auto_reject(repo, pr_number, pr_key)
                return {"status": "rejected", "message": f"PR #{pr_number} auto-rejected after 4 cycles"}

            return {"status": "changes_requested", "message": f"PR #{pr_number} rejected (cycle {cycles}/4)"}

        return {"status": "ignored", "message": "Review state not actionable"}

    async def _auto_merge(self, repo: Dict, pr_number: int) -> None:
        """
        Auto-merge PR on approval.

        POST /api/v1/repos/{owner}/{repo}/pulls/{index}/merge
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}/merge"

        response = requests.post(
            url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json={
                "Do": "merge",
                "MergeMessageField": f"Auto-merged PR #{pr_number} after approval",
                "delete_branch_after_merge": True
            },
            timeout=10
        )

        if response.status_code == 200:
            log_event("pr_merged", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.workspace)
        else:
            log_event("pr_merge_failed", {
                "pr": pr_number,
                "status": response.status_code,
                "error": response.text
            }, self.workspace)

    async def _escalate_to_architect(self, repo: Dict, pr_number: int) -> None:
        """
        Escalate to lead_architect after 3 rejections.
        Add comment requesting architect review.
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"

        comment = """🚨 **Architect Escalation Required**

This PR has been rejected **3 times** by integrity_guard.

@lead_architect - Please review the **APPROACH**, not just implementation details.

### Your Task:
1. Is the developer solving the right problem?
2. Is the architecture sound?
3. Are there simpler alternatives?
4. What specific guidance can help unblock this?

**This is the last chance before auto-reject.**"""

        requests.post(
            url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json={"body": comment},
            timeout=10
        )

        log_event("pr_escalated", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.workspace)

    async def _auto_reject(self, repo: Dict, pr_number: int, pr_key: str) -> None:
        """
        Auto-reject PR after 4 review cycles.
        Close PR and create Requirements Review Issue.
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]

        # Close PR
        close_url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}"
        requests.patch(
            close_url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json={"state": "closed"},
            timeout=10
        )

        # Add final comment
        comment_url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        requests.post(
            comment_url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json={"body": "❌ **Auto-rejected** after 4 review cycles. Requirements Issue created."},
            timeout=10
        )

        # Create Requirements Review Issue
        await self._create_requirements_issue(repo, pr_number, pr_key)

        log_event("pr_rejected", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.workspace)

        # Cleanup tracking
        self.pr_review_cycles.pop(pr_key, None)
        self.pr_failure_reasons.pop(pr_key, None)

    async def _create_requirements_issue(self, repo: Dict, pr_number: int, pr_key: str) -> None:
        """
        Create Requirements Review Issue after auto-reject.
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues"

        failure_reasons = self.pr_failure_reasons.get(pr_key, [])
        reasons_text = "\n".join([
            f"**Cycle {r['cycle']}** ({r['timestamp']}): {r['reason']}"
            for r in failure_reasons
        ])

        body = f"""## 🔄 Requirements Review: PR #{pr_number} Failed After 4 Cycles

**Original PR**: #{pr_number} (closed)

### Failure Summary
Rejected **4 times** despite architect consultation.

### Rejection Reasons
{reasons_text}

### Root Cause Analysis
Why did this fail even with guidance?
- [ ] Requirements unclear?
- [ ] Technical limitation?
- [ ] Model capability issue?
- [ ] Missing context/references?

### Next Steps
- [ ] Refine requirements
- [ ] Add examples/fixtures
- [ ] Simplify scope
- [ ] Assign to different agent/seat
"""

        requests.post(
            url,
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            json={
                "title": f"Requirements Review: PR #{pr_number} failed after 4 cycles",
                "body": body,
                "labels": ["requirements-review", "auto-rejected"]
            },
            timeout=10
        )

    async def _handle_pr_merged(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle PR merged event.
        Trigger sandbox deployment.
        """
        pr = payload["pull_request"]
        repo = payload["repository"]
        pr_number = pr["number"]
        owner = repo["owner"]["login"]
        repo_name = repo["name"]

        log_event("pr_merged", {
            "pr": pr_number,
            "repo": f"{owner}/{repo_name}",
            "merged_by": pr.get("merged_by", {}).get("login", "unknown")
        }, self.workspace)

        # Trigger sandbox deployment
        await self._trigger_sandbox_deployment(owner, repo_name, pr)

        return {"status": "success", "message": f"PR #{pr_number} merged, sandbox deployment triggered"}

    async def _trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: Dict) -> None:
        """
        Trigger sandbox deployment after PR merge.

        This will eventually call SandboxOrchestrator.create_sandbox()
        For now, just log the event.
        """
        # TODO: Integrate with SandboxOrchestrator
        # from orket.services.sandbox_orchestrator import SandboxOrchestrator
        # orchestrator = SandboxOrchestrator(...)
        # await orchestrator.create_sandbox(...)

        log_event("sandbox_deployment_triggered", {
            "repo": f"{owner}/{repo_name}",
            "pr": pr["number"],
            "branch": pr["head"]["ref"]
        }, self.workspace)

        print(f"🚀 Sandbox deployment triggered for {owner}/{repo_name} PR #{pr['number']}")
