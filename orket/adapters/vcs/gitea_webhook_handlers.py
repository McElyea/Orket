from __future__ import annotations

import asyncio
import re
from typing import Any

from pydantic import ValidationError

from orket.adapters.vcs.gitea_webhook_payloads import (
    PullRequestMergedWebhookPayload,
    PullRequestOpenedWebhookPayload,
    PullRequestReviewWebhookPayload,
    webhook_payload_validation_error,
)
from orket.logging import log_event
from orket.schema import CardStatus


def _response_error(*, action: str, response: Any) -> str | None:
    status_code = int(getattr(response, "status_code", 0) or 0)
    if 200 <= status_code < 300:
        return None
    detail = f"{action} failed with status {status_code}"
    response_text = str(getattr(response, "text", "") or "").strip()
    if response_text:
        detail = f"{detail}: {response_text}"
    return detail


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
        reviewer = review["user"]["login"]
        review_state = review["state"]

        log_event("pr_review", {"pr": pr_key, "reviewer": reviewer, "state": review_state}, self.handler.workspace)

        if review_state == "approved":
            merge_error = await self.auto_merge(repo, pr_number)
            if merge_error is not None:
                return {"status": "error", "message": f"PR #{pr_number} approved but merge failed: {merge_error}"}
            return {"status": "success", "message": f"PR #{pr_number} approved and merged"}

        if review_state == "changes_requested":
            repo_full_name = f"{repo['owner']['login']}/{repo['name']}"
            cycles = await self.handler.db.increment_pr_cycle(repo_full_name, pr_number)
            reason = review.get("body") or "No reason provided"
            await self.handler.db.add_failure_reason(repo_full_name, pr_number, reviewer, reason)

            if cycles == 3:
                escalation_error = await self.escalate_to_architect(repo, pr_number)
                if escalation_error is not None:
                    return {
                        "status": "error",
                        "message": (
                            f"PR #{pr_number} hit architect escalation threshold "
                            f"but escalation failed: {escalation_error}"
                        ),
                    }
                return {"status": "escalated", "message": f"PR #{pr_number} escalated to architect"}
            if cycles >= 4:
                rejection_error = await self.auto_reject(repo, pr_number, repo_full_name)
                if rejection_error is not None:
                    return {
                        "status": "error",
                        "message": f"PR #{pr_number} hit auto-reject threshold but rejection failed: {rejection_error}",
                    }
                return {"status": "rejected", "message": f"PR #{pr_number} auto-rejected after 4 cycles"}
            return {"status": "changes_requested", "message": f"PR #{pr_number} rejected (cycle {cycles}/4)"}

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
            log_event(
                "pr_merge_failed",
                {"pr": pr_number, "status": getattr(response, "status_code", None), "error": error},
                self.handler.workspace,
            )
            return error
        log_event("pr_merged", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.handler.workspace)
        return None

    async def escalate_to_architect(self, repo: dict[str, Any], pr_number: int) -> str | None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = (
            "Architect escalation required. This PR has been rejected 3 times by integrity_guard. "
            "@lead_architect please review approach and provide unblock guidance. "
            "This is the last chance before auto-reject."
        )
        response = await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment},
        )
        error = _response_error(action=f"architect escalation comment for PR #{pr_number}", response=response)
        if error is not None:
            log_event(
                "pr_escalation_failed",
                {"pr": pr_number, "repo": f"{owner}/{repo_name}", "error": error},
                self.handler.workspace,
            )
            return error
        log_event("pr_escalated", {"pr": pr_number, "repo": f"{owner}/{repo_name}"}, self.handler.workspace)
        return None

    async def auto_reject(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> str | None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        repo_key = f"{owner}/{repo_name}"

        close_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/pulls/{pr_number}"
        close_response = await self.handler.client.patch(
            close_url,
            headers={"Content-Type": "application/json"},
            json={"state": "closed"},
        )
        close_error = _response_error(action=f"PR #{pr_number} close", response=close_response)
        if close_error is not None:
            log_event(
                "pr_reject_failed",
                {"pr": pr_number, "repo": repo_key, "step": "close_pr", "error": close_error},
                self.handler.workspace,
            )
            return close_error

        comment_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment_response = await self.handler.client.post(
            comment_url,
            headers={"Content-Type": "application/json"},
            json={"body": "Auto-rejected after 4 review cycles. Requirements Issue created."},
        )
        comment_error = _response_error(action=f"auto-reject comment for PR #{pr_number}", response=comment_response)
        if comment_error is not None:
            log_event(
                "pr_reject_failed",
                {"pr": pr_number, "repo": repo_key, "step": "comment", "error": comment_error},
                self.handler.workspace,
            )
            return comment_error

        requirements_error = await self.handler.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)
        if requirements_error is not None:
            normalized_requirements_error = str(requirements_error)
            log_event(
                "pr_reject_failed",
                {"pr": pr_number, "repo": repo_key, "step": "requirements_issue", "error": normalized_requirements_error},
                self.handler.workspace,
            )
            return normalized_requirements_error

        log_event("pr_rejected", {"pr": pr_number, "repo": repo_key}, self.handler.workspace)
        await self.handler.db.close_pr_cycle(repo_full_name, pr_number, status="rejected")
        return None


class PRLifecycleHandler:
    """Handles PR opened/merged lifecycle events."""

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def handle_pr_opened(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            validated_payload = PullRequestOpenedWebhookPayload.model_validate(payload)
        except ValidationError as exc:
            return webhook_payload_validation_error(event_type="pull_request", exc=exc)

        pr = validated_payload.pull_request.model_dump()
        repo = validated_payload.repository.model_dump()
        pr_number = pr["number"]
        repo_full_name = f"{repo['owner']['login']}/{repo['name']}"

        log_event(
            "pr_opened",
            {"pr": pr_number, "repo": repo_full_name, "action": validated_payload.action},
            self.handler.workspace,
        )
        issue_match = re.search(r"ISSUE-[A-Z0-9]+", pr["title"])
        issue_id = issue_match.group(0) if issue_match else None
        if not issue_id:
            return {"status": "ignored", "message": "No issue ID found in PR title"}

        from orket.orchestration.engine import OrchestrationEngine

        engine = OrchestrationEngine(self.handler.workspace)
        await engine.cards.update_status(issue_id, CardStatus.CODE_REVIEW)
        task = asyncio.create_task(engine.run_card(issue_id))
        def _log_task_error(completed: asyncio.Task[Any]) -> None:
            exc = completed.exception()
            if exc is not None:
                log_event(
                    "webhook_run_card_error",
                    {"issue_id": issue_id, "error": str(exc)},
                    self.handler.workspace,
                )

        task.add_done_callback(_log_task_error)
        return {"status": "success", "message": f"PR #{pr_number} review triggered for {issue_id}"}

    async def handle_pr_merged(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            validated_payload = PullRequestMergedWebhookPayload.model_validate(payload)
        except ValidationError as exc:
            return webhook_payload_validation_error(event_type="pull_request", exc=exc)

        pr = validated_payload.pull_request.model_dump(exclude_none=True)
        repo = validated_payload.repository.model_dump()
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
        deployment_result = await self.handler.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)
        if deployment_result.get("skipped", False):
            return {
                "status": "skipped",
                "message": (
                    f"PR #{pr_number} merged. Sandbox deployment skipped: "
                    f"{deployment_result.get('reason', 'unsupported capability')}"
                ),
            }
        if not deployment_result.get("ok", False):
            return {
                "status": "degraded",
                "message": (
                    f"PR #{pr_number} merged, but sandbox deployment failed: "
                    f"{deployment_result.get('error', 'unknown error')}"
                ),
            }
        return {"status": "success", "message": f"PR #{pr_number} merged, sandbox deployment triggered"}

    async def create_requirements_issue(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> str | None:
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues"

        failure_reasons = await self.handler.db.get_failure_reasons(repo_full_name, pr_number)
        reasons_text = "\n".join(
            [
                f"Cycle {reason['cycle_number']} ({reason['created_at']}): {reason['reason']}"
                for reason in failure_reasons
            ]
        )
        body = (
            f"Requirements Review: PR #{pr_number} failed after 4 cycles\n\n"
            f"Original PR: #{pr_number} (closed)\n\n"
            f"Rejection Reasons:\n{reasons_text}\n"
        )
        label_ids = await self._resolve_issue_label_ids(owner, repo_name, ["requirements-review", "auto-rejected"])
        issue_payload: dict[str, Any] = {
            "title": f"Requirements Review: PR #{pr_number} failed after 4 cycles",
            "body": body,
        }
        if label_ids:
            issue_payload["labels"] = label_ids

        response = await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json=issue_payload,
        )
        error = _response_error(action=f"requirements issue creation for PR #{pr_number}", response=response)
        if error is not None:
            log_event(
                "requirements_issue_creation_failed",
                {"pr": pr_number, "repo": f"{owner}/{repo_name}", "error": error},
                self.handler.workspace,
            )
            return error
        return None

    async def _resolve_issue_label_ids(self, owner: str, repo_name: str, label_names: list[str]) -> list[int]:
        labels_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/labels"
        response = await self.handler.client.get(labels_url)
        error = _response_error(action=f"requirements issue label lookup for {owner}/{repo_name}", response=response)
        if error is not None:
            log_event(
                "requirements_issue_label_lookup_failed",
                {"repo": f"{owner}/{repo_name}", "error": error},
                self.handler.workspace,
            )
            return []
        try:
            payload = response.json()
        except (TypeError, ValueError, AttributeError):
            log_event(
                "requirements_issue_label_lookup_failed",
                {"repo": f"{owner}/{repo_name}", "error": "label lookup returned invalid json"},
                self.handler.workspace,
            )
            return []
        if not isinstance(payload, list):
            log_event(
                "requirements_issue_label_lookup_failed",
                {"repo": f"{owner}/{repo_name}", "error": "label lookup returned non-list payload"},
                self.handler.workspace,
            )
            return []

        label_ids: list[int] = []
        matched_names: set[str] = set()
        expected_names = {name.lower(): name for name in label_names}
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip().lower()
            label_id = entry.get("id")
            if name in expected_names and isinstance(label_id, int) and label_id > 0:
                label_ids.append(label_id)
                matched_names.add(name)

        missing = [name for name in label_names if name.lower() not in matched_names]
        if missing:
            log_event(
                "requirements_issue_labels_missing",
                {"repo": f"{owner}/{repo_name}", "missing_labels": missing},
                self.handler.workspace,
            )
        return label_ids


class SandboxDeploymentHandler:
    """Handles sandbox deployment and PR comment publication."""

    _UNSUPPORTED_REASON = "Orket is not yet positioned to produce deployable code projects from this merge path."

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: dict[str, Any]) -> dict[str, Any]:
        repo_full_name = f"{owner}/{repo_name}"
        pr_number = pr["number"]
        log_event(
            "sandbox_deployment_skipped",
            {
                "repo": repo_full_name,
                "pr": pr_number,
                "reason": self._UNSUPPORTED_REASON,
            },
            self.handler.workspace,
        )
        return {
            "ok": False,
            "skipped": True,
            "reason": self._UNSUPPORTED_REASON,
        }

    async def add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = (
            "Sandbox deployed successfully.\n\n"
            f"- API: {sandbox.api_url}\n"
            f"- Frontend: {sandbox.frontend_url}\n"
            f"- Database: {sandbox.tech_stack.value}\n\n"
            f"Sandbox ID: {sandbox.id}"
        )
        response = await self.handler.client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"body": comment},
        )
        error = _response_error(action=f"sandbox comment for PR #{pr_number}", response=response)
        if error is not None:
            raise RuntimeError(error)
