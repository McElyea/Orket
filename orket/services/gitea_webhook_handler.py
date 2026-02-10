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
import httpx
from datetime import datetime
from dotenv import load_dotenv

from orket.logging import log_event
from orket.services.webhook_db import WebhookDatabase
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.sandbox import TechStack, SandboxRegistry

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

        # SQLite database for review cycle tracking
        self.db = WebhookDatabase()

        # Sandbox orchestrator for deployment
        self.sandbox_registry = SandboxRegistry()
        self.sandbox_orchestrator = SandboxOrchestrator(
            workspace_root=self.workspace,
            registry=self.sandbox_registry
        )

        # Persistent HTTP client
        self.client = httpx.AsyncClient(auth=self.auth, timeout=10.0)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

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
        elif event_type == "pull_request":
            action = payload.get("action")
            if action in ["opened", "synchronized"]:
                return await self._handle_pr_opened(payload)
            elif action == "closed":
                if payload["pull_request"].get("merged"):
                    return await self._handle_pr_merged(payload)

        return {"status": "ignored", "message": f"Event type {event_type} not handled"}

    async def _handle_pr_opened(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Handle PR opened or updated events.
        Triggers the autonomous CODE_REVIEW process.
        """
        pr = payload["pull_request"]
        repo = payload["repository"]
        pr_number = pr["number"]
        repo_full_name = f"{repo['owner']['login']}/{repo['name']}"

        log_event("pr_opened", {
            "pr": pr_number,
            "repo": repo_full_name,
            "action": payload.get("action")
        }, self.workspace)

        # In a real environment, we'd map the PR to an Orket Issue
        # For now, we'll try to find the issue ID from the PR title (e.g. "[ISSUE-123] ...")
        import re
        issue_match = re.search(r"ISSUE-[A-Z0-9]+", pr["title"])
        issue_id = issue_match.group(0) if issue_match else None

        if not issue_id:
            # Fallback: Check if we have a mapping in our DB
            # For this MVP, we'll assume the PR *is* the work for the current epic
            return {"status": "ignored", "message": "No issue ID found in PR title"}

        # Trigger the Orchestration Engine for a Code Review turn
        from orket.orchestration.engine import OrchestrationEngine
        engine = OrchestrationEngine(self.workspace)
        
        # We run the card, and the engine's traction loop will find it in READY or CODE_REVIEW
        # We must ensure the card is in CODE_REVIEW state
        await engine.cards.update_status(issue_id, "code_review")
        
        # Start execution
        import asyncio
        asyncio.create_task(engine.run_card(issue_id))

        return {"status": "success", "message": f"PR #{pr_number} review triggered for {issue_id}"}

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
            repo_full_name = f"{repo['owner']['login']}/{repo['name']}"
            cycles = await self.db.increment_pr_cycle(repo_full_name, pr_number)

            # Store failure reason
            reason = review.get("body", "No reason provided")
            await self.db.add_failure_reason(repo_full_name, pr_number, reviewer, reason)

            # Cycle 3: Escalate to architect
            if cycles == 3:
                await self._escalate_to_architect(repo, pr_number)
                return {"status": "escalated", "message": f"PR #{pr_number} escalated to architect"}

            # Cycle 4+: Auto-reject
            elif cycles >= 4:
                await self._auto_reject(repo, pr_number, repo_full_name)
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

        response = await self.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "Do": "merge",
                "MergeMessageField": f"Auto-merged PR #{pr_number} after approval",
                "delete_branch_after_merge": True
            }
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

        await self.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment}
        )

        log_event("pr_escalated", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.workspace)

    async def _auto_reject(self, repo: Dict, pr_number: int, repo_full_name: str) -> None:
        """
        Auto-reject PR after 4 review cycles.
        Close PR and create Requirements Review Issue.
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]

        # Close PR
        close_url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}"
        await self.client.patch(
            close_url,
            headers={"Content-Type": "application/json"},
            json={"state": "closed"}
        )

        # Add final comment
        comment_url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        await self.client.post(
            comment_url,
            headers={"Content-Type": "application/json"},
            json={"body": "❌ **Auto-rejected** after 4 review cycles. Requirements Issue created."},
        )

        # Create Requirements Review Issue
        await self._create_requirements_issue(repo, pr_number, repo_full_name)

        log_event("pr_rejected", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.workspace)

        # Mark PR cycle as rejected in database
        await self.db.close_pr_cycle(repo_full_name, pr_number, status="rejected")

    async def _create_requirements_issue(self, repo: Dict, pr_number: int, repo_full_name: str) -> None:
        """
        Create Requirements Review Issue after auto-reject.
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues"

        failure_reasons = await self.db.get_failure_reasons(repo_full_name, pr_number)
        reasons_text = "\n".join([
            f"**Cycle {r['cycle_number']}** ({r['created_at']}): {r['reason']}"
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

        await self.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "title": f"Requirements Review: PR #{pr_number} failed after 4 cycles",
                "body": body,
                "labels": ["requirements-review", "auto-rejected"]
            }
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
        repo_full_name = f"{owner}/{repo_name}"

        log_event("pr_merged", {
            "pr": pr_number,
            "repo": repo_full_name,
            "merged_by": pr.get("merged_by", {}).get("login", "unknown")
        }, self.workspace)

        # Mark PR cycle as merged in database
        await self.db.close_pr_cycle(repo_full_name, pr_number, status="merged")

        # Trigger sandbox deployment
        await self._trigger_sandbox_deployment(owner, repo_name, pr)

        return {"status": "success", "message": f"PR #{pr_number} merged, sandbox deployment triggered"}

    async def _trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: Dict) -> None:
        """
        Trigger sandbox deployment after PR merge.
        Creates a Docker Compose sandbox for the merged code.
        """
        repo_full_name = f"{owner}/{repo_name}"
        pr_number = pr["number"]
        branch = pr["head"]["ref"]

        # Clone the repo to local workspace (for now, assume it's already there)
        # In production, this would clone from Gitea
        workspace_path = self.workspace / "sandboxes" / repo_name

        # Determine tech stack from repository metadata
        # For now, default to FastAPI + React + Postgres
        # TODO: Read from .orket.json or repository config
        tech_stack = TechStack.FASTAPI_REACT_POSTGRES

        # Create rock_id from repo and PR
        rock_id = f"{repo_name}-pr{pr_number}"

        try:
            sandbox = await self.sandbox_orchestrator.create_sandbox(
                rock_id=rock_id,
                project_name=f"{repo_name} (PR #{pr_number})",
                tech_stack=tech_stack,
                workspace_path=str(workspace_path)
            )

            log_event("sandbox_deployed", {
                "repo": repo_full_name,
                "pr": pr_number,
                "sandbox_id": sandbox.id,
                "api_url": sandbox.api_url,
                "frontend_url": sandbox.frontend_url
            }, self.workspace)

            # Comment on PR with sandbox URLs
            await self._add_sandbox_comment(owner, repo_name, pr_number, sandbox)

            print(f"🚀 Sandbox deployed for {repo_full_name} PR #{pr_number}")
            print(f"   API: {sandbox.api_url}")
            print(f"   Frontend: {sandbox.frontend_url}")

        except Exception as e:
            log_event("sandbox_deployment_failed", {
                "repo": repo_full_name,
                "pr": pr_number,
                "error": str(e)
            }, self.workspace)
            print(f"❌ Sandbox deployment failed: {e}")

    async def _add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox) -> None:
        """Add comment to PR with sandbox deployment URLs."""
        url = f"{self.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"

        comment = f"""🚀 **Sandbox Deployed Successfully**

Your code has been deployed to a live environment for testing:

- API: [{sandbox.api_url}]({sandbox.api_url})
- Frontend: [{sandbox.frontend_url}]({sandbox.frontend_url})
- Database: {sandbox.tech_stack.value}

**Sandbox ID**: `{sandbox.id}`

The sandbox will remain active during the Bug Fix Phase. Bugs discovered will automatically create Issues for remediation.
"""

        await self.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment}
        )
