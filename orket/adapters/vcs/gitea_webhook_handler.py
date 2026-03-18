"""Gitea webhook entrypoint with delegated policy handlers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from orket.adapters.vcs.gitea_webhook_handlers import (
    PRLifecycleHandler,
    PRReviewHandler,
    SandboxDeploymentHandler,
)
from orket.adapters.vcs.webhook_db import WebhookDatabase
from orket.domain.sandbox import SandboxRegistry
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class GiteaWebhookHandler:
    """Application service that routes incoming Gitea webhook events."""

    def __init__(self, gitea_url: str = "http://localhost:3000", workspace: Optional[Path] = None):
        self.gitea_url = gitea_url
        self.gitea_user = os.getenv("GITEA_ADMIN_USER", "Orket")
        self.gitea_password = os.getenv("GITEA_ADMIN_PASSWORD")
        if not self.gitea_password:
            raise RuntimeError(
                "GITEA_ADMIN_PASSWORD environment variable is not set. Set it before initializing the webhook handler."
            )
        self.workspace = workspace or Path.cwd()
        self.auth = (self.gitea_user, self.gitea_password)

        self.db = WebhookDatabase()
        self.sandbox_registry = SandboxRegistry()
        self.sandbox_orchestrator = SandboxOrchestrator(
            workspace_root=self.workspace,
            registry=self.sandbox_registry,
        )
        self.client = httpx.AsyncClient(auth=self.auth, timeout=10.0)

        self.review = PRReviewHandler(self)
        self.lifecycle = PRLifecycleHandler(self)
        self.sandbox = SandboxDeploymentHandler(self)

    async def _handle_pr_review(self, payload: Dict[str, Any]) -> Dict[str, str]:
        return await self.review.handle_pr_review(payload)

    async def _auto_merge(self, repo: Dict[str, Any], pr_number: int) -> None:
        await self.review.auto_merge(repo, pr_number)

    async def _escalate_to_architect(self, repo: Dict[str, Any], pr_number: int) -> None:
        await self.review.escalate_to_architect(repo, pr_number)

    async def _auto_reject(self, repo: Dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        await self.review.auto_reject(repo, pr_number, repo_full_name)

    async def _handle_pr_opened(self, payload: Dict[str, Any]) -> Dict[str, str]:
        return await self.lifecycle.handle_pr_opened(payload)

    async def _handle_pr_merged(self, payload: Dict[str, Any]) -> Dict[str, str]:
        return await self.lifecycle.handle_pr_merged(payload)

    async def _create_requirements_issue(self, repo: Dict[str, Any], pr_number: int, repo_full_name: str) -> None:
        await self.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)

    async def _trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: Dict[str, Any]) -> None:
        await self.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)

    async def _add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        await self.sandbox.add_sandbox_comment(owner, repo_name, pr_number, sandbox)

    async def close(self) -> None:
        await self.client.aclose()

    async def handle_webhook(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, str]:
        if event_type == "pull_request_review":
            return await self._handle_pr_review(payload)

        if event_type == "pull_request":
            action = payload.get("action")
            if action in ["opened", "synchronized"]:
                return await self._handle_pr_opened(payload)
            if action == "closed" and payload["pull_request"].get("merged"):
                return await self._handle_pr_merged(payload)

        return {"status": "ignored", "message": f"Event type {event_type} not handled"}
