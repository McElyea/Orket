from __future__ import annotations

from typing import Any

from orket.application.services.gitea_webhook_support import _response_error


class SandboxDeploymentHandler:
    """Handles sandbox deployment and PR comment publication."""

    _UNSUPPORTED_REASON = "Orket is not yet positioned to produce deployable code projects from this merge path."

    def __init__(self, handler: Any) -> None:
        self.handler = handler

    async def trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: dict[str, Any]) -> dict[str, Any]:
        repo_full_name = f"{owner}/{repo_name}"
        pr_number = pr["number"]
        await self.handler._log_event(
            "sandbox_deployment_skipped", {"repo": repo_full_name, "pr": pr_number, "reason": self._UNSUPPORTED_REASON}
        )
        return {"ok": False, "skipped": True, "reason": self._UNSUPPORTED_REASON}

    async def add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        url = f"{self.handler.gitea_url}/api/v1/repos/{owner}/{repo_name}/issues/{pr_number}/comments"
        comment = f"Sandbox deployed successfully.\n\n- API: {sandbox.api_url}\n- Frontend: {sandbox.frontend_url}\n- Database: {sandbox.tech_stack.value}\n\nSandbox ID: {sandbox.id}"
        response = await self.handler.client.post(
            url, headers={"Content-Type": "application/json"}, json={"body": comment}
        )
        error = _response_error(action=f"sandbox comment for PR #{pr_number}", response=response)
        if error is not None:
            raise RuntimeError(error)
