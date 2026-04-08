from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_repositories import AsyncPendingGateRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_operator_service import (
    KernelActionControlPlaneOperatorService,
)
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.application.services.kernel_action_control_plane_view_service import KernelActionControlPlaneViewService
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.logging import log_event
from orket.runtime_paths import resolve_control_plane_db_path


def _dict_result(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dict_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
            continue
        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump()
            if isinstance(dumped, dict):
                rows.append(dict(dumped))
    return rows


def _string_list_map(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, row in value.items():
        if not isinstance(row, list):
            continue
        normalized[str(key)] = [str(item) for item in row]
    return normalized


class EngineControlPlaneServices:
    """Explicit owner for engine-scoped control-plane composition."""

    def __init__(
        self,
        *,
        pending_gates: Any,
        control_plane_repository: Any,
        control_plane_execution_repository: Any,
        control_plane_publication: Any,
        tool_approval_control_plane_operator: Any,
        kernel_action_control_plane: Any,
        kernel_action_control_plane_operator: Any,
        kernel_action_control_plane_view: Any,
    ) -> None:
        self.pending_gates = pending_gates
        self.control_plane_repository = control_plane_repository
        self.control_plane_execution_repository = control_plane_execution_repository
        self.control_plane_publication = control_plane_publication
        self.tool_approval_control_plane_operator = tool_approval_control_plane_operator
        self.kernel_action_control_plane = kernel_action_control_plane
        self.kernel_action_control_plane_operator = kernel_action_control_plane_operator
        self.kernel_action_control_plane_view = kernel_action_control_plane_view


def build_engine_control_plane_services(*, db_path: str | Path) -> EngineControlPlaneServices:
    """Build the engine's control-plane dependencies in one explicit composition step."""
    control_plane_db_path = resolve_control_plane_db_path()
    control_plane_repository = AsyncControlPlaneRecordRepository(control_plane_db_path)
    control_plane_execution_repository = AsyncControlPlaneExecutionRepository(control_plane_db_path)
    control_plane_publication = ControlPlanePublicationService(repository=control_plane_repository)
    return EngineControlPlaneServices(
        pending_gates=AsyncPendingGateRepository(str(db_path)),
        control_plane_repository=control_plane_repository,
        control_plane_execution_repository=control_plane_execution_repository,
        control_plane_publication=control_plane_publication,
        tool_approval_control_plane_operator=ToolApprovalControlPlaneOperatorService(
            publication=control_plane_publication
        ),
        kernel_action_control_plane=KernelActionControlPlaneService(
            execution_repository=control_plane_execution_repository,
            publication=control_plane_publication,
        ),
        kernel_action_control_plane_operator=KernelActionControlPlaneOperatorService(
            publication=control_plane_publication
        ),
        kernel_action_control_plane_view=KernelActionControlPlaneViewService(
            record_repository=control_plane_repository,
            execution_repository=control_plane_execution_repository,
        ),
    )


class SandboxManager:
    """Focused sandbox operations extracted from OrchestrationEngine."""

    def __init__(self, sandbox_orchestrator: Any) -> None:
        self._sandbox_orchestrator = sandbox_orchestrator

    async def list_active(self) -> list[dict[str, Any]]:
        if self._sandbox_orchestrator is None:
            return []
        list_method = getattr(self._sandbox_orchestrator, "list_sandboxes", None)
        if callable(list_method):
            return _dict_rows(await list_method())
        registry = self._sandbox_orchestrator.registry
        return [item.model_dump() for item in registry.list_active()]

    async def stop(self, sandbox_id: str, *, operator_actor_ref: str | None = None) -> None:
        if self._sandbox_orchestrator is None:
            return None
        stop_method = getattr(self._sandbox_orchestrator, "stop_sandbox", None)
        if callable(stop_method):
            await stop_method(sandbox_id, operator_actor_ref=operator_actor_ref)
            return None
        await self._sandbox_orchestrator.delete_sandbox(sandbox_id, operator_actor_ref=operator_actor_ref)


class SessionController:
    """Focused session lifecycle controls extracted from OrchestrationEngine."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    async def halt(self, session_id: str) -> bool:
        from orket.state import runtime_state

        tasks = await runtime_state.get_tasks(session_id)
        cancelled = False
        for task in tasks:
            if task.done():
                continue
            task.cancel()
            cancelled = True
        if cancelled:
            log_event("session_halted", {"session_id": session_id}, self.workspace_root)
            return True
        return False


class CardArchiver:
    """Focused card archival operations extracted from OrchestrationEngine."""

    def __init__(self, cards_repo: Any) -> None:
        self._cards = cards_repo

    async def archive_card(self, card_id: str, *, archived_by: str = "system", reason: str | None = None) -> bool:
        return bool(await self._cards.archive_card(card_id, archived_by=archived_by, reason=reason))

    async def archive_cards(
        self,
        card_ids: list[str],
        *,
        archived_by: str = "system",
        reason: str | None = None,
    ) -> dict[str, list[str]]:
        return _string_list_map(await self._cards.archive_cards(card_ids, archived_by=archived_by, reason=reason))

    async def archive_build(self, build_id: str, *, archived_by: str = "system", reason: str | None = None) -> int:
        return int(await self._cards.archive_build(build_id, archived_by=archived_by, reason=reason))

    async def archive_related_cards(
        self,
        related_tokens: list[str],
        *,
        archived_by: str = "system",
        reason: str | None = None,
        limit: int = 500,
    ) -> dict[str, list[str]]:
        card_ids = await self._cards.find_related_card_ids(related_tokens, limit=limit)
        return _string_list_map(await self._cards.archive_cards(card_ids, archived_by=archived_by, reason=reason))


class KernelGatewayFacade:
    """Focused kernel passthrough operations extracted from OrchestrationEngine."""

    def __init__(self, kernel_gateway: Any) -> None:
        self._gw = kernel_gateway

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.start_run(request))

    def execute_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.execute_turn(request))

    def finish_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.finish_run(request))

    def resolve_capability(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.resolve_capability(request))

    def authorize_tool_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.authorize_tool_call(request))

    def replay_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.replay_run(request))

    def compare_runs(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.compare_runs(request))

    def projection_pack(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.projection_pack(request))

    def admit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.admit_proposal(request))

    def commit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.commit_proposal(request))

    def end_session(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.end_session(request))

    def list_ledger_events(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.list_ledger_events(request))

    def rebuild_pending_approvals(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.rebuild_pending_approvals(request))

    def replay_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.replay_action_lifecycle(request))

    def audit_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return _dict_result(self._gw.audit_action_lifecycle(request))

    def run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: list[dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _dict_result(
            self._gw.run_lifecycle(
                workflow_id=workflow_id,
                execute_turn_requests=execute_turn_requests,
                finish_outcome=finish_outcome,
                start_request=start_request,
            )
        )


class ReplayDiagnosticsService:
    """Artifact-backed replay diagnostics. This is not a canonical replay-verdict authority path."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    def replay_turn_diagnostics(
        self,
        *,
        session_id: str,
        issue_id: str,
        turn_index: int,
        role: str | None = None,
    ) -> dict[str, Any]:
        run_root = self.workspace_root / "observability" / session_id / issue_id
        if not run_root.exists():
            raise FileNotFoundError(f"No observability artifacts found for run={session_id} issue={issue_id}")

        prefix = f"{turn_index:03d}_"
        candidates = [path for path in run_root.iterdir() if path.is_dir() and path.name.startswith(prefix)]
        if role:
            role_suffix = role.lower().replace(" ", "_")
            candidates = [path for path in candidates if path.name.endswith(role_suffix)]
        if not candidates:
            raise FileNotFoundError(f"No turn artifacts found for turn_index={turn_index}")

        target = sorted(candidates)[0]
        checkpoint_path = target / "checkpoint.json"
        messages_path = target / "messages.json"
        model_path = target / "model_response.txt"
        parsed_tools_path = target / "parsed_tool_calls.json"

        def _read_json(path: Path) -> Any:
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))

        return {
            "diagnostics_class": "artifact_observability_only",
            "turn_dir": str(target),
            "checkpoint": _read_json(checkpoint_path),
            "messages": _read_json(messages_path),
            "model_response": model_path.read_text(encoding="utf-8") if model_path.exists() else None,
            "parsed_tool_calls": _read_json(parsed_tools_path),
        }
