"""Gitea webhook entrypoint with delegated policy handlers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib import parse

import httpx
from pydantic import ValidationError

from orket.adapters.vcs.gitea_webhook_handlers import (
    PRLifecycleHandler,
    PRReviewHandler,
    SandboxDeploymentHandler,
)
from orket.adapters.vcs.gitea_webhook_payloads import (
    PullRequestDispatchWebhookPayload,
    webhook_payload_validation_error,
)
from orket.adapters.vcs.webhook_db import WebhookDatabase
from orket.core.domain.sandbox import SandboxRegistry
from orket.services.sandbox_orchestrator import SandboxOrchestrator

logger = logging.getLogger(__name__)


class GiteaWebhookHandler:
    """Application service that routes incoming Gitea webhook events.

    `allow_insecure` is only for local development against plaintext Gitea.
    """

    def __init__(
        self,
        gitea_url: str = "https://localhost:3000",
        workspace: Path | None = None,
        *,
        sandbox_orchestrator: SandboxOrchestrator | None = None,
        lifecycle_db_path: str | None = None,
        allow_insecure: bool = False,
    ):
        self.gitea_url = _validate_gitea_url(gitea_url, allow_insecure=allow_insecure)
        self.gitea_user = os.getenv("GITEA_ADMIN_USER", "Orket")
        self.gitea_password = os.getenv("GITEA_ADMIN_PASSWORD")
        if not self.gitea_password:
            raise RuntimeError(
                "GITEA_ADMIN_PASSWORD environment variable is not set. Set it before initializing the webhook handler."
            )
        self.workspace = workspace or Path.cwd()
        self.auth = (self.gitea_user, self.gitea_password)

        self.db = WebhookDatabase(db_path=self.workspace / ".orket" / "durable" / "db" / "webhook.db")
        if sandbox_orchestrator is not None:
            self.sandbox_orchestrator = sandbox_orchestrator
            self.sandbox_registry = sandbox_orchestrator.registry
        else:
            self.sandbox_registry = SandboxRegistry()
            self.sandbox_orchestrator = SandboxOrchestrator(
                workspace_root=self.workspace,
                registry=self.sandbox_registry,
                lifecycle_db_path=lifecycle_db_path,
            )
        self.client = httpx.AsyncClient(auth=self.auth, timeout=10.0)

        self.review = PRReviewHandler(self)
        self.lifecycle = PRLifecycleHandler(self)
        self.sandbox = SandboxDeploymentHandler(self)

    async def _handle_pr_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.review.handle_pr_review(payload)

    async def _auto_merge(self, repo: dict[str, Any], pr_number: int) -> None:
        await self.review.auto_merge(repo, pr_number)

    async def _escalate_to_architect(self, repo: dict[str, Any], pr_number: int) -> None:
        await self.review.escalate_to_architect(repo, pr_number)

    async def _auto_reject(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        await self.review.auto_reject(repo, pr_number, repo_full_name)

    async def _handle_pr_opened(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.lifecycle.handle_pr_opened(payload)

    async def _handle_pr_merged(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.lifecycle.handle_pr_merged(payload)

    async def _create_requirements_issue(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        await self.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)

    async def _trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: dict[str, Any]) -> None:
        await self.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)

    async def _add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        await self.sandbox.add_sandbox_comment(owner, repo_name, pr_number, sandbox)

    async def __aenter__(self) -> GiteaWebhookHandler:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.aclose()

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if event_type == "pull_request_review":
            return await self._handle_pr_review(payload)

        if event_type == "pull_request":
            try:
                dispatch_payload = PullRequestDispatchWebhookPayload.model_validate(payload)
            except ValidationError as exc:
                return webhook_payload_validation_error(event_type="pull_request", exc=exc)

            action = dispatch_payload.action
            if action in {"opened", "synchronized"}:
                return await self._handle_pr_opened(payload)
            if action == "closed" and dispatch_payload.pull_request.merged:
                return await self._handle_pr_merged(payload)

        return {"status": "ignored", "message": f"Event type {event_type} not handled"}


def _validate_gitea_url(gitea_url: str, *, allow_insecure: bool) -> str:
    resolved_url = str(gitea_url or "").strip().rstrip("/")
    parsed = parse.urlparse(resolved_url)
    scheme = str(parsed.scheme or "").lower()
    if scheme == "https":
        return resolved_url
    if scheme == "http" and allow_insecure:
        logger.warning("gitea_webhook_insecure_url_allowed")
        return resolved_url
    raise ValueError("Gitea webhook handler requires an https:// gitea_url unless allow_insecure=True.")
