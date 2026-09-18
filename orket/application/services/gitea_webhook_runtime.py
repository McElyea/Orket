"""Application authority for Gitea review policy, admitted work and resource lifetime."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar

from pydantic import ValidationError

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.vcs.gitea_webhook_client import build_webhook_http_client, validate_gitea_url
from orket.adapters.vcs.gitea_webhook_event import normalize_gitea_review
from orket.adapters.vcs.webhook_db import WebhookDatabase
from orket.application.services.application_runtime_lifetime import ApplicationRuntimeLifetime
from orket.application.services.gitea_pr_lifecycle_service import PRLifecycleHandler
from orket.application.services.gitea_pr_review_service import PRReviewHandler
from orket.application.services.gitea_sandbox_webhook_service import SandboxDeploymentHandler
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.webhook_configuration import WebhookConfiguration, capture_webhook_configuration
from orket.application.services.webhook_ingress_policy import WebhookIngressPolicy
from orket.core.contracts.gitea_webhook import PullRequestDispatchWebhookPayload, webhook_payload_validation_error
from orket.core.domain.sandbox import SandboxRegistry
from orket.logging import log_event
from orket.runtime_paths import resolve_runtime_db_path, resolve_sandbox_lifecycle_db_path
from orket.schema import CardStatus
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class GiteaWebhookHandler(ApplicationRuntimeLifetime):
    """Construct through the owned builder on async paths; direct sync embeddings own close."""

    _runtime_name: ClassVar[str] = "Webhook"

    def __init__(
        self,
        gitea_url: str = "https://localhost:3000",
        workspace: Path | None = None,
        *,
        sandbox_orchestrator: SandboxOrchestrator | None = None,
        lifecycle_db_path: str | None = None,
        allow_insecure: bool = False,
        environment: Mapping[str, str] | None = None,
        configuration: WebhookConfiguration | None = None,
        runtime_inputs: RuntimeInputService | None = None,
        require_credentials: bool = True,
    ) -> None:
        super().__init__()
        self.configuration = configuration or capture_webhook_configuration(
            workspace,
            environment=environment,
            require_config=False,
        )
        self.workspace = self.configuration.project_root
        self.runtime_inputs = runtime_inputs or RuntimeInputService()
        self.ingress = WebhookIngressPolicy(self.configuration, monotonic=self.runtime_inputs.monotonic_seconds)
        self.gitea_url = validate_gitea_url(gitea_url, allow_insecure=allow_insecure)
        self.gitea_user, self.gitea_password = self.configuration.user, self.configuration.password
        if require_credentials and not self.gitea_password:
            raise RuntimeError(
                "GITEA_ADMIN_PASSWORD environment variable is not set. Set it before initializing the webhook handler."
            )
        self.db = WebhookDatabase(db_path=self.workspace / ".orket/durable/db/webhook.db")
        self._review_db_path = resolve_runtime_db_path(
            invocation_root=self.configuration.invocation_root,
            environment=self.configuration.environment,
        )
        if sandbox_orchestrator is not None:
            self.sandbox_orchestrator = sandbox_orchestrator
            self.sandbox_registry = sandbox_orchestrator.registry
        else:
            self.sandbox_registry = SandboxRegistry()
            self.sandbox_orchestrator = SandboxOrchestrator(
                workspace_root=self.workspace,
                registry=self.sandbox_registry,
                lifecycle_db_path=resolve_sandbox_lifecycle_db_path(
                    lifecycle_db_path,
                    invocation_root=self.configuration.invocation_root,
                    environment=self.configuration.environment,
                ),
                environment=self.configuration.environment,
            )
        self.review, self.lifecycle, self.sandbox = (
            PRReviewHandler(self),
            PRLifecycleHandler(self),
            SandboxDeploymentHandler(self),
        )
        self.client = build_webhook_http_client(username=self.gitea_user, password=self.gitea_password)

    async def _log_event(self, name: str, payload: dict[str, Any]) -> None:
        await run_owned_thread(lambda: log_event(name, payload, self.workspace), label="webhook-event-publication")

    async def _handle_pr_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.review.handle_pr_review(payload)

    async def _auto_merge(self, repo: dict[str, Any], pr_number: int) -> str | None:
        return await self.review.auto_merge(repo, pr_number)

    async def _escalate_to_architect(self, repo: dict[str, Any], pr_number: int) -> str | None:
        return await self.review.escalate_to_architect(repo, pr_number)

    async def _auto_reject(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> str | None:
        return await self.review.auto_reject(repo, pr_number, repo_full_name)

    async def _handle_pr_opened(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.lifecycle.handle_pr_opened(payload)

    async def _handle_pr_merged(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self.lifecycle.handle_pr_merged(payload)

    async def _create_requirements_issue(self, repo: dict[str, Any], pr_number: int, repo_full_name: str) -> str | None:
        return await self.lifecycle.create_requirements_issue(repo, pr_number, repo_full_name)

    async def _trigger_sandbox_deployment(self, owner: str, repo_name: str, pr: dict[str, Any]) -> dict[str, Any]:
        return await self.sandbox.trigger_sandbox_deployment(owner, repo_name, pr)

    async def _add_sandbox_comment(self, owner: str, repo_name: str, pr_number: int, sandbox: Any) -> None:
        await self.sandbox.add_sandbox_comment(owner, repo_name, pr_number, sandbox)

    async def __aenter__(self) -> GiteaWebhookHandler:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.close()

    async def _close_final_resource(self) -> None:
        await run_owned_io(self.client.aclose, label="webhook-http-close", preserve_failure=True)

    async def handle_webhook(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        captured = json.loads(json.dumps(payload, allow_nan=False))
        result: dict[str, Any] = {}

        async def invoke() -> None:
            nonlocal result
            result = await self._dispatch(event_type, captured)

        await self.run_request(invoke)
        return result

    async def _dispatch(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.gitea_password:
            raise RuntimeError("GITEA_ADMIN_PASSWORD is not configured for this application.")
        native_review = event_type in {"pull_request_approved", "pull_request_rejected"} or (
            event_type == "pull_request_comment" and payload.get("action") == "reviewed"
        )
        if event_type == "pull_request_review" or native_review:
            try:
                normalized = normalize_gitea_review(event_type, payload)
            except ValueError as exc:
                return webhook_payload_validation_error(event_type=event_type, exc=exc)
            return await self._handle_pr_review(normalized)
        if event_type == "pull_request":
            try:
                dispatch_payload = PullRequestDispatchWebhookPayload.model_validate(payload)
            except ValidationError as exc:
                return webhook_payload_validation_error(event_type="pull_request", exc=exc)
            if dispatch_payload.action in {"opened", "synchronized"}:
                return await self._handle_pr_opened(payload)
            if dispatch_payload.action == "closed" and dispatch_payload.pull_request.merged:
                return await self._handle_pr_merged(payload)
        return {"status": "ignored", "message": f"Event type {event_type} not handled"}

    async def _start_review(self, issue_id: str) -> None:
        from orket.orchestration.engine import OrchestrationEngine

        created = []

        def construct():
            engine = OrchestrationEngine(
                self.workspace,
                config_root=self.workspace,
                db_path=self._review_db_path,
                runtime_inputs=self.runtime_inputs,
            )
            created.append(engine)
            return engine

        try:
            engine = await run_owned_thread(construct, label="webhook-review-bootstrap")
        except asyncio.CancelledError:
            if created:
                await run_owned_io(created[0].close, label="webhook-review-bootstrap-close", preserve_failure=True)
            raise
        registered = False
        try:
            self.register_owned_resource(engine)
            registered = True
            await run_owned_io(
                lambda: engine.cards.update_status(issue_id, CardStatus.CODE_REVIEW),
                label="webhook-review-admission",
                preserve_failure=True,
            )
            self.start_background(lambda: self._run_review(engine, issue_id))
        except (Exception, asyncio.CancelledError):  # admission boundary retains engine cleanup on failure
            if registered:
                self.release_owned_resource(engine)
            await run_owned_io(engine.close, label="webhook-review-admission-close", preserve_failure=True)
            raise

    async def _run_review(self, engine: Any, issue_id: str) -> None:
        try:
            # Until this coroutine starts, the parent owns the constructed engine.
            self.release_owned_resource(engine)
            result = await engine.run_card(issue_id)
            if not result.succeeded:
                await self._log_event(
                    "webhook_run_card_error", {"issue_id": issue_id, "outcome": result.model_dump(mode="json")}
                )
        finally:
            await run_owned_io(engine.close, label="webhook-review-close", preserve_failure=True)


async def build_webhook_runtime(
    configuration: WebhookConfiguration, *, runtime_inputs: RuntimeInputService | None = None
) -> GiteaWebhookHandler:
    created = []

    def construct():
        handler = GiteaWebhookHandler(
            gitea_url=configuration.gitea_url,
            configuration=configuration,
            runtime_inputs=runtime_inputs,
            allow_insecure=configuration.allow_insecure,
            require_credentials=False,
        )
        created.append(handler)
        return handler

    try:
        return await run_owned_thread(construct, label="webhook-runtime-bootstrap")
    except asyncio.CancelledError:
        if created:
            await created[0].close()
        raise
