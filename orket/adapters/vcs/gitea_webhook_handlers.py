from __future__ import annotations

import asyncio
import re
from typing import Any, Dict

import httpx

from orket.domain.sandbox import TechStack
from orket.logging import log_event
from orket.schema import CardStatus


class PRReviewHandler:
    """Handles PR review events and review-cycle policy."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def handle_pr_review(self, payload: Dict[str, Any]) -> Dict[str, str]:
        pr = payload["pull_request"]
        review = payload["review"]
        repo = payload["repository"]

        pr_number = pr["number"]
        pr_key = f"{repo['owner']['login']}/{repo['name']}/#{pr_number}"
        reviewer = review["user"]["login"]
        review_state = review["state"]

        log_event("pr_review", {"pr": pr_key, "reviewer": reviewer, "state": review_state}, self.handler.workspace)

        if review_state == "approved":
            await self.auto_merge(repo, pr_number)
            return {"status": "success", "message": f"PR #{pr_number} approved and merged"}

        if review_state == "changes_requested":
            repo_full_name = f"{repo['owner']['login']}/{repo['name']}"
            cycles = await self.handler.db.increment_pr_cycle(repo_full_name, pr_number)
            reason = review.get("body", "No reason provided")
            await self.handler.db.add_failure_reason(repo_full_name, pr_number, reviewer, reason)

            if cycles == 3:
                await self.escalate_to_architect(repo, pr_number)
                return {"status": "escalated", "message": f"PR #{pr_number} escalated to architect"}
            if cycles >= 4:
                await self.auto_reject(repo, pr_number, repo_full_name)
                return {"status": "rejected", "message": f"PR #{pr_number} auto-rejected after 4 cycles"}
            return {"status": "changes_requested", "message": f"PR #{pr_number} rejected (cycle {cycles}/4)"}

        return {"status": "ignored", "message": "Review state not actionable"}

    async def auto_merge(self, repo: Dict[str, Any], pr_number: int) -> None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}/merge"

        response = await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "Do": "merge",
                "MergeMessageField": f"Auto-merged PR #{pr_number} after approval",
                "delete_branch_after_merge": True,
            },
        )

        if response.status_code == 200:
            log_event("pr_merged", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.handler.workspace)
        else:
            log_event(
                "pr_merge_failed",
                {"pr": pr_number, "status": response.status_code, "error": response.text},
                self.handler.workspace,
            )

    async def escalate_to_architect(self, repo: Dict[str, Any], pr_number: int) -> None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = (
            "Architect escalation required. This PR has been rejected 3 times by integrity_guard. "
            "@lead_architect please review approach and provide unblock guidance. "
            "This is the last chance before auto-reject."
        )
        await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment},
        )
        log_event("pr_escalated", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.handler.workspace)

    async def auto_reject(self, repo: Dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]

        close_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}"
        await self.handler.client.patch(
            close_url,
            headers={"Content-Type": "application/json"},
            json={"state": "closed"},
        )

        comment_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        await self.handler.client.post(
            comment_url,
            headers={"Content-Type": "application/json"},
            json={"body": "Auto-rejected after 4 review cycles. Requirements Issue created."},
        )

        await self.handler.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)
        log_event("pr_rejected", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.handler.workspace)
        await self.handler.db.close_pr_cycle(repo_full_name, pr_number, status="rejected")


class PRLifecycleHandler:
    """Handles PR opened/merged lifecycle events."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def handle_pr_opened(self, payload: Dict[str, Any]) -> Dict[str, str]:
        pr = payload["pull_request"]
        repo = payload["repository"]
        pr_number = pr["number"]
        repo_full_name = f"{repo['owner']['login']}/{repo['name']}"

        log_event("pr_opened", {"pr": pr_number, "repo": repo_full_name, "action": payload.get("action")}, self.handler.workspace)
        issue_match = re.search(r"ISSUE-[A-Z0-9]+", pr["title"])
        issue_id = issue_match.group(0) if issue_match else None
        if not issue_id:
            return {"status": "ignored", "message": "No issue ID found in PR title"}

        from orket.orchestration.engine import OrchestrationEngine

        engine = OrchestrationEngine(self.handler.workspace)
        await engine.cards.update_status(issue_id, CardStatus.CODE_REVIEW)
        asyncio.create_task(engine.run_card(issue_id))
        return {"status": "success", "message": f"PR #{pr_number} review triggered for {issue_id}"}

    async def handle_pr_merged(self, payload: Dict[str, Any]) -> Dict[str, str]:
        pr = payload["pull_request"]
        repo = payload["repository"]
        pr_number = pr["number"]
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        repo_full_name = f"{owner}/{repo_name}"

        log_event(
            "pr_merged",
            {"pr": pr_number, "repo": repo_full_name, "merged_by": pr.get("merged_by", {}).get("login", "unknown")},
            self.handler.workspace,
        )
        await self.handler.db.close_pr_cycle(repo_full_name, pr_number, status="merged")
        await self.handler.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)
        return {"status": "success", "message": f"PR #{pr_number} merged, sandbox deployment triggered"}

    async def create_requirements_issue(self, repo: Dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues"

        failure_reasons = await self.handler.db.get_failure_reasons(repo_full_name, pr_number)
        reasons_text = "\n".join(
            [f"Cycle {reason['cycle_number']} ({reason['created_at']}): {reason['reason']}" for reason in failure_reasons]
        )
        body = (
            f"Requirements Review: PR #{pr_number} failed after 4 cycles\n\n"
            f"Original PR: #{pr_number} (closed)\n\n"
            f"Rejection Reasons:\n{reasons_text}\n"
        )

        await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "title": f"Requirements Review: PR #{pr_number} failed after 4 cycles",
                "body": body,
                "labels": ["requirements-review", "auto-rejected"],
            },
        )


class SandboxDeploymentHandler:
    """Handles sandbox deployment and PR comment publication."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: Dict[str, Any]) -> None:
        repo_full_name = f"{owner}/{repo_name}"
        pr_number = pr["number"]
        workspace_path = self.handler.workspace / "sandboxes" / repo_name

        try:
            sandbox = await self.handler.sandbox_orchestrator.create_sandbox(
                rock_id=f"{repo_name}-pr{pr_number}",
                project_name=f"{repo_name} (PR #{pr_number})",
                tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                workspace_path=str(workspace_path),
            )
            log_event(
                "sandbox_deployed",
                {
                    "repo": repo_full_name,
                    "pr": pr_number,
                    "sandbox_id": sandbox.id,
                    "api_url": sandbox.api_url,
                    "frontend_url": sandbox.frontend_url,
                },
                self.handler.workspace,
            )
            await self.add_sandbox_comment(owner, repo_name, pr_number, sandbox)
        except (RuntimeError, ValueError, OSError, httpx.HTTPError) as exc:
            log_event(
                "sandbox_deployment_failed",
                {"repo": repo_full_name, "pr": pr_number, "error": str(exc)},
                self.handler.workspace,
            )

    async def add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = (
            "Sandbox deployed successfully.\n\n"
            f"- API: {sandbox.api_url}\n"
            f"- Frontend: {sandbox.frontend_url}\n"
            f"- Database: {sandbox.tech_stack.value}\n\n"
            f"Sandbox ID: {sandbox.id}"
        )
        await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment},
        )
