from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from orket.application.services.gitea_webhook_support import _response_error, _webhook_event_id
from orket.core.contracts.gitea_webhook import (
    PullRequestReviewWebhookPayload,
    webhook_payload_validation_error,
)

MAX_PR_REVIEW_CYCLES = 3


class PRReviewHandler:
    """Handles PR review events and review-cycle policy."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def handle_pr_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            validated_payload = PullRequestReviewWebhookPayload.model_validate(payload)
        except ValidationError as exc:
            return webhook_payload_validation_error(event_type="pull_request_review", exc=exc)
        pr = validated_payload.pull_request.model_dump()
        review = validated_payload.review.model_dump(exclude_none=True)
        repo = validated_payload.repository.model_dump()
        pr_number = pr["number"]
        pr_key = f"{repo['owner']['login']}/{repo['name']}/#{pr_number}"
        repo_full_name = f"{repo['owner']['login']}/{repo['name']}"
        event_id = _webhook_event_id(payload)
        if event_id:
            recorded = await self.handler.db.try_record_webhook_event(
                event_id=event_id, event_type="pull_request_review", pr_key=f"{repo_full_name}#{pr_number}"
            )
            if not recorded:
                await self.handler._log_event(
                    "webhook_event_duplicate_skipped",
                    {"event_type": "pull_request_review", "event_id": event_id, "pr": pr_key},
                )
                return {"status": "duplicate", "message": f"Duplicate webhook event skipped: {event_id}"}
        reviewer = review["user"]["login"]
        review_state = review["state"]
        await self.handler._log_event("pr_review", {"pr": pr_key, "reviewer": reviewer, "state": review_state})
        if review_state == "approved":
            merge_error = await self.auto_merge(repo, pr_number)
            if merge_error is not None:
                return {"status": "error", "message": f"PR #{pr_number} approved but merge failed: {merge_error}"}
            return {"status": "success", "message": f"PR #{pr_number} approved and merged"}
        if review_state == "changes_requested":
            cycles = await self.handler.db.increment_pr_cycle(repo_full_name, pr_number)
            reason = review.get("body") or "No reason provided"
            await self.handler.db.add_failure_reason(repo_full_name, pr_number, reviewer, reason)
            if cycles >= MAX_PR_REVIEW_CYCLES + 1:
                rejection_error = await self.auto_reject(repo, pr_number, repo_full_name)
                if rejection_error is not None:
                    return {
                        "status": "error",
                        "message": f"PR #{pr_number} hit auto-reject threshold but rejection failed: {rejection_error}",
                    }
                return {
                    "status": "rejected",
                    "message": f"PR #{pr_number} auto-rejected after {MAX_PR_REVIEW_CYCLES + 1} cycles",
                }
            if cycles >= MAX_PR_REVIEW_CYCLES:
                escalation_error = await self.escalate_to_architect(repo, pr_number)
                if escalation_error is not None:
                    return {
                        "status": "error",
                        "message": f"PR #{pr_number} hit architect escalation threshold but escalation failed: {escalation_error}",
                    }
                return {"status": "escalated", "message": f"PR #{pr_number} escalated to architect"}
            return {
                "status": "changes_requested",
                "message": f"PR #{pr_number} rejected (cycle {cycles}/{MAX_PR_REVIEW_CYCLES + 1})",
            }
        return {"status": "ignored", "message": "Review state not actionable"}

    async def auto_merge(self, repo: dict[str, Any], pr_number: int) -> str | None:
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
        error = _response_error(action=f"PR #{pr_number} merge", response=response)
        if error is not None:
            await self.handler._log_event(
                "pr_merge_failed", {"pr": pr_number, "status": getattr(response, "status_code", None), "error": error}
            )
            return error
        await self.handler._log_event("pr_merged", {"pr": pr_number, "repo": f"{owner}/{repo_name}"})
        return None

    async def escalate_to_architect(self, repo: dict[str, Any], pr_number: int) -> str | None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = "Architect escalation required. This PR has been rejected 3 times by integrity_guard. @lead_architect please review approach and provide unblock guidance. This is the last chance before auto-reject."
        response = await self.handler.client.post(
            url, headers={"Content-Type": "application/json"}, json={"body": comment}
        )
        error = _response_error(action=f"architect escalation comment for PR #{pr_number}", response=response)
        if error is not None:
            await self.handler._log_event(
                "pr_escalation_failed", {"pr": pr_number, "repo": f"{owner}/{repo_name}", "error": error}
            )
            return error
        await self.handler._log_event("pr_escalated", {"pr": pr_number, "repo": f"{owner}/{repo_name}"})
        return None

    async def auto_reject(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> str | None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        repo_key = f"{owner}/{repo_name}"
        close_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}"
        close_response = await self.handler.client.patch(
            close_url, headers={"Content-Type": "application/json"}, json={"state": "closed"}
        )
        close_error = _response_error(action=f"PR #{pr_number} close", response=close_response)
        if close_error is not None:
            await self.handler._log_event(
                "pr_reject_failed", {"pr": pr_number, "repo": repo_key, "step": "close_pr", "error": close_error}
            )
            return close_error
        comment_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment_response = await self.handler.client.post(
            comment_url,
            headers={"Content-Type": "application/json"},
            json={"body": "Closed after 4 review cycles. Requirements review requested."},
        )
        comment_error = _response_error(action=f"auto-reject comment for PR #{pr_number}", response=comment_response)
        if comment_error is not None:
            await self.handler._log_event(
                "pr_reject_failed", {"pr": pr_number, "repo": repo_key, "step": "comment", "error": comment_error}
            )
            return comment_error
        requirements_error = await self.handler.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)
        if requirements_error is not None:
            normalized_requirements_error = str(requirements_error)
            await self.handler._log_event(
                "pr_reject_failed",
                {
                    "pr": pr_number,
                    "repo": repo_key,
                    "step": "requirements_issue",
                    "error": normalized_requirements_error,
                },
            )
            return normalized_requirements_error
        await self.handler._log_event("pr_rejected", {"pr": pr_number, "repo": repo_key})
        await self.handler.db.close_pr_cycle(repo_full_name, pr_number, status="rejected")
        return None
