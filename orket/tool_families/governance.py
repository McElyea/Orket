from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from orket.core.types import CardStatus
from orket.tool_families.base import BaseTools


class GovernanceTools(BaseTools):
    """Process/governance-oriented tools separated from toolbox wiring mechanics."""

    def __init__(self, workspace_root: Path, references: List[Path], cards: Any):
        super().__init__(workspace_root, references)
        self.cards = cards

    def nominate_card(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from orket.logging import log_event

        context = context or {}
        log_event("card_nomination", {**args, "nominated_by": context.get("role")}, self.workspace_root, role="SYS")
        return {"ok": True, "message": "Nomination recorded."}

    async def report_credits(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
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

    def refinement_proposal(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from orket.logging import log_event

        log_event("refinement_proposed", args, self.workspace_root, role="SYS")
        return {"ok": True, "message": "Proposal logged."}

    async def request_excuse(self, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
