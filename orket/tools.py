from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.adapters.tools.families import (
    AcademyTools,
    BaseTools,
    CardManagementTools,
    FileSystemTools,
    GovernanceTools,
    ReforgerTools,
    VisionTools,
)
from orket.adapters.tools.runtime import ToolRuntimeExecutor
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.runtime_paths import resolve_runtime_db_path

if TYPE_CHECKING:
    from orket.adapters.storage.async_card_repository import AsyncCardRepository
    from orket.core.policies.tool_gate import ToolGate
    from orket.schema import OrganizationConfig


class ToolBox:
    def __init__(
        self,
        policy: Any,
        workspace_root: str,
        references: list[str],
        db_path: str | None = None,
        cards_repo: AsyncCardRepository | None = None,
        tool_gate: ToolGate | None = None,
        organization: OrganizationConfig | None = None,
        decision_nodes: DecisionNodeRegistry | None = None,
        runtime_executor: ToolRuntimeExecutor | None = None,
    ) -> None:
        self.root = Path(workspace_root)
        self.refs = [Path(r) for r in references]
        self.db_path = resolve_runtime_db_path(db_path)
        self.organization = organization
        self.decision_nodes = decision_nodes if decision_nodes is not None else DecisionNodeRegistry()
        self.tool_strategy_node = self.decision_nodes.resolve_tool_strategy(self.organization)
        self.runtime_executor = runtime_executor or ToolRuntimeExecutor()
        self.fs = FileSystemTools(self.root, self.refs)
        self.vision = VisionTools(self.root, self.refs)
        self.cards = CardManagementTools(
            self.root,
            self.refs,
            db_path=self.db_path,
            cards_repo=cards_repo,
            tool_gate=tool_gate,
        )
        self.governance = GovernanceTools(self.root, self.refs, cards=self.cards)
        self.academy = AcademyTools(self.root, self.refs)
        self.reforger = ReforgerTools(self.root, self.refs)

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tool_map = get_tool_map(self)
        if tool_name not in tool_map:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}

        tool_fn = tool_map[tool_name]
        resolved_context = dict(context or {})
        return await self.runtime_executor.invoke(
            tool_fn,
            args,
            context=resolved_context,
            tool_name=tool_name,
            tool_timeout_seconds=_resolve_tool_timeout_seconds(resolved_context),
            workspace=self.root,
        )

    def nominate_card(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.governance.nominate_card(args, context=dict(context or {}))

    async def report_credits(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.governance.report_credits(args, context=dict(context or {}))

    def refinement_proposal(
        self,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.governance.refinement_proposal(args, context=dict(context or {}))

    async def request_excuse(
        self,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.governance.request_excuse(args, context=dict(context or {}))


def get_tool_map(toolbox: ToolBox) -> dict[str, Callable[..., Any]]:
    return toolbox.tool_strategy_node.compose(toolbox)


def _resolve_tool_timeout_seconds(context: dict[str, Any]) -> float:
    runtime_limits = context.get("tool_runtime_limits")
    candidates = [
        context.get("tool_timeout_seconds"),
        runtime_limits.get("max_execution_time") if isinstance(runtime_limits, dict) else None,
        context.get("max_tool_execution_time"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            value = float(candidate)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 60.0


__all__ = [
    "BaseTools",
    "FileSystemTools",
    "VisionTools",
    "CardManagementTools",
    "GovernanceTools",
    "AcademyTools",
    "ReforgerTools",
    "ToolBox",
    "get_tool_map",
]
