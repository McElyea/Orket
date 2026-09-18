from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from orket.application.services.gitea_webhook_support import _response_error
from orket.core.contracts.gitea_webhook import (
    PullRequestMergedWebhookPayload,
    PullRequestOpenedWebhookPayload,
    webhook_payload_validation_error,
)


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
        await self.handler._log_event(
            "pr_opened", {"pr": pr_number, "repo": repo_full_name, "action": validated_payload.action}
        )
        issue_match = re.search("ISSUE-[A-Z0-9]+", pr["title"])
        issue_id = issue_match.group(0) if issue_match else None
        if not issue_id:
            return {"status": "ignored", "message": "No issue ID found in PR title"}
        await self.handler._start_review(issue_id)
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
        await self.handler._log_event(
            "pr_merged",
            {"pr": pr_number, "repo": repo_full_name, "merged_by": pr.get("merged_by", {}).get("login", "unknown")},
        )
        await self.handler.db.close_pr_cycle(repo_full_name, pr_number, status="merged")
        deployment_result = await self.handler.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)
        if deployment_result.get("skipped", False):
            return {
                "status": "skipped",
                "message": f"PR #{pr_number} merged. Sandbox deployment skipped: {deployment_result.get('reason', 'unsupported capability')}",
            }
        if not deployment_result.get("ok", False):
            return {
                "status": "degraded",
                "message": f"PR #{pr_number} merged, but sandbox deployment failed: {deployment_result.get('error', 'unknown error')}",
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
        body = f"Requirements Review: PR #{pr_number} failed after 4 cycles\n\nOriginal PR: #{pr_number} (closed)\n\nRejection Reasons:\n{reasons_text}\n"
        label_ids = await self._resolve_issue_label_ids(owner, repo_name, ["requirements-review", "auto-rejected"])
        issue_payload: dict[str, Any] = {
            "title": f"Requirements Review: PR #{pr_number} failed after 4 cycles",
            "body": body,
        }
        if label_ids:
            issue_payload["labels"] = label_ids
        response = await self.handler.client.post(url, headers={"Content-Type": "application/json"}, json=issue_payload)
        error = _response_error(action=f"requirements issue creation for PR #{pr_number}", response=response)
        if error is not None:
            await self.handler._log_event(
                "requirements_issue_creation_failed", {"pr": pr_number, "repo": f"{owner}/{repo_name}", "error": error}
            )
            return error
        return None

    async def _resolve_issue_label_ids(self, owner: str, repo_name: str, label_names: list[str]) -> list[int]:
        labels_url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/labels"
        response = await self.handler.client.get(labels_url)
        error = _response_error(action=f"requirements issue label lookup for {owner}/{repo_name}", response=response)
        if error is not None:
            await self.handler._log_event(
                "requirements_issue_label_lookup_failed", {"repo": f"{owner}/{repo_name}", "error": error}
            )
            return []
        try:
            payload = response.json()
        except (TypeError, ValueError, AttributeError):
            await self.handler._log_event(
                "requirements_issue_label_lookup_failed",
                {"repo": f"{owner}/{repo_name}", "error": "label lookup returned invalid json"},
            )
            return []
        if not isinstance(payload, list):
            await self.handler._log_event(
                "requirements_issue_label_lookup_failed",
                {"repo": f"{owner}/{repo_name}", "error": "label lookup returned non-list payload"},
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
            if name in expected_names and isinstance(label_id, int) and (label_id > 0):
                label_ids.append(label_id)
                matched_names.add(name)
        missing = [name for name in label_names if name.lower() not in matched_names]
        if missing:
            await self.handler._log_event(
                "requirements_issue_labels_missing", {"repo": f"{owner}/{repo_name}", "missing_labels": missing}
            )
        return label_ids
