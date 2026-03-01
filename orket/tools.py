from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from orket.decision_nodes.registry import DecisionNodeRegistry
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
from orket.runtime_paths import resolve_runtime_db_path

if TYPE_CHECKING:
    from orket.adapters.storage.async_card_repository import AsyncCardRepository
    from orket.schema import OrganizationConfig
    from orket.core.policies.tool_gate import ToolGate


class ToolBox:
    def __init__(
        self,
        policy,
        workspace_root: str,
        references: List[str],
        db_path: Optional[str] = None,
        cards_repo: Optional["AsyncCardRepository"] = None,
        tool_gate: Optional["ToolGate"] = None,
        organization: Optional["OrganizationConfig"] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
        runtime_executor: Optional[ToolRuntimeExecutor] = None,
    ):
        self.root = Path(workspace_root)
        self.refs = [Path(r) for r in references]
        self.db_path = resolve_runtime_db_path(db_path)
        self.organization = organization
        self.decision_nodes = decision_nodes or DecisionNodeRegistry()
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

    async def execute(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        tool_map = get_tool_map(self)
        if tool_name not in tool_map:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}

        tool_fn = tool_map[tool_name]
        return await self.runtime_executor.invoke(tool_fn, args, context=context)

    def nominate_card(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.governance.nominate_card(args, context=context)

    async def report_credits(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return await self.governance.report_credits(args, context=context)

    def refinement_proposal(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return self.governance.refinement_proposal(args, context=context)

    async def request_excuse(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        return await self.governance.request_excuse(args, context=context)


def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    return toolbox.tool_strategy_node.compose(toolbox)


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

