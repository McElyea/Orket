from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.logging import log_event


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
