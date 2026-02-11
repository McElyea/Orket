from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from orket.core.types import CardStatus
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.tool_families import AcademyTools, BaseTools, CardManagementTools, FileSystemTools, VisionTools
from orket.tool_runtime import ToolRuntimeExecutor

if TYPE_CHECKING:
    from orket.infrastructure.async_card_repository import AsyncCardRepository
    from orket.schema import OrganizationConfig
    from orket.services.tool_gate import ToolGate


class ToolBox:
    def __init__(
        self,
        policy,
        workspace_root: str,
        references: List[str],
        db_path: str = "orket_persistence.db",
        cards_repo: Optional["AsyncCardRepository"] = None,
        tool_gate: Optional["ToolGate"] = None,
        organization: Optional["OrganizationConfig"] = None,
        decision_nodes: Optional[DecisionNodeRegistry] = None,
        runtime_executor: Optional[ToolRuntimeExecutor] = None,
    ):
        self.root = Path(workspace_root)
        self.refs = [Path(r) for r in references]
        self.db_path = db_path
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
        self.academy = AcademyTools(self.root, self.refs)

    async def execute(self, tool_name: str, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        tool_map = get_tool_map(self)
        if tool_name not in tool_map:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}

        tool_fn = tool_map[tool_name]
        return await self.runtime_executor.invoke(tool_fn, args, context=context)

    def nominate_card(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.logging import log_event

        context = context or {}
        log_event("card_nomination", {**args, "nominated_by": context.get("role")}, self.root, role="SYS")
        return {"ok": True, "message": "Nomination recorded."}

    async def report_credits(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        issue_id = context.get("issue_id") or args.get("issue_id")
        amount = args.get("amount", 0.0)
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            return {"ok": False, "error": "Invalid params"}
        if not issue_id or amount <= 0:
            return {"ok": False, "error": "Invalid params"}

        add_credits_fn = getattr(self.cards.cards, "add_credits", None)
        if add_credits_fn is None:
            return {"ok": False, "error": "Credits repository adapter unavailable"}

        await add_credits_fn(issue_id, amount)
        return {"ok": True, "message": f"Reported {amount} credits."}

    def refinement_proposal(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.logging import log_event

        log_event("refinement_proposed", args, self.root, role="SYS")
        return {"ok": True, "message": "Proposal logged."}

    async def request_excuse(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        issue_id = context.get("issue_id") or args.get("issue_id")
        if not issue_id:
            return {"ok": False, "error": "No active Issue"}

        await self.cards.cards.update_status(issue_id, CardStatus.WAITING_FOR_DEVELOPER)

        reason = args.get("reason")
        if reason:
            comment_context = {**context, "issue_id": issue_id, "role": context.get("role", "SYS")}
            await self.cards.add_issue_comment({"comment": reason}, context=comment_context)

        return {"ok": True, "message": "Excuse requested."}


def get_tool_map(toolbox: ToolBox) -> Dict[str, Callable]:
    return toolbox.tool_strategy_node.compose(toolbox)


__all__ = [
    "BaseTools",
    "FileSystemTools",
    "VisionTools",
    "CardManagementTools",
    "AcademyTools",
    "ToolBox",
    "get_tool_map",
]
