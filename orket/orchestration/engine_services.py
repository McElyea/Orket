from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from orket.logging import log_event


class SandboxManager:
    """Focused sandbox operations extracted from OrchestrationEngine."""

    def __init__(self, sandbox_orchestrator: Any) -> None:
        self._sandbox_orchestrator = sandbox_orchestrator

    async def list_active(self) -> List[Dict[str, Any]]:
        if self._sandbox_orchestrator is None:
            return []
        registry = self._sandbox_orchestrator.registry
        return [item.model_dump() for item in registry.list_active()]

    async def stop(self, sandbox_id: str) -> None:
        if self._sandbox_orchestrator is None:
            return None
        await self._sandbox_orchestrator.delete_sandbox(sandbox_id)


class SessionController:
    """Focused session lifecycle controls extracted from OrchestrationEngine."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root

    async def halt(self, session_id: str) -> None:
        from orket.state import runtime_state

        task = await runtime_state.get_task(session_id)
        if task:
            task.cancel()
            log_event("session_halted", {"session_id": session_id}, self.workspace_root)


class CardArchiver:
    """Focused card archival operations extracted from OrchestrationEngine."""

    def __init__(self, cards_repo: Any) -> None:
        self._cards = cards_repo

    async def archive_card(self, card_id: str, *, archived_by: str = "system", reason: Optional[str] = None) -> bool:
        return await self._cards.archive_card(card_id, archived_by=archived_by, reason=reason)

    async def archive_cards(
        self,
        card_ids: List[str],
        *,
        archived_by: str = "system",
        reason: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        return await self._cards.archive_cards(card_ids, archived_by=archived_by, reason=reason)

    async def archive_build(self, build_id: str, *, archived_by: str = "system", reason: Optional[str] = None) -> int:
        return await self._cards.archive_build(build_id, archived_by=archived_by, reason=reason)

    async def archive_related_cards(
        self,
        related_tokens: List[str],
        *,
        archived_by: str = "system",
        reason: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, List[str]]:
        card_ids = await self._cards.find_related_card_ids(related_tokens, limit=limit)
        return await self._cards.archive_cards(card_ids, archived_by=archived_by, reason=reason)


class KernelGatewayFacade:
    """Focused kernel passthrough operations extracted from OrchestrationEngine."""

    def __init__(self, kernel_proxy: Any) -> None:
        self._kernel_proxy = kernel_proxy

    def start_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.start_run(request)

    def execute_turn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.execute_turn(request)

    def finish_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.finish_run(request)

    def resolve_capability(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.resolve_capability(request)

    def authorize_tool_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.authorize_tool_call(request)

    def replay_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.replay_run(request)

    def compare_runs(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self._kernel_proxy.compare_runs(request)

    def run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: List[Dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._kernel_proxy.run_lifecycle(
            workflow_id=workflow_id,
            execute_turn_requests=execute_turn_requests,
            finish_outcome=finish_outcome,
            start_request=start_request,
        )
