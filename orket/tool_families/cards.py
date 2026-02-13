from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from orket.tool_families.base import BaseTools

if TYPE_CHECKING:
    from orket.infrastructure.async_card_repository import AsyncCardRepository
    from orket.core.policies.tool_gate import ToolGate


class CardManagementTools(BaseTools):
    def __init__(
        self,
        workspace_root: Path,
        references: List[Path],
        db_path: str = "orket_persistence.db",
        cards_repo: Optional["AsyncCardRepository"] = None,
        tool_gate: Optional["ToolGate"] = None,
    ):
        super().__init__(workspace_root, references)
        from orket.infrastructure.async_card_repository import AsyncCardRepository

        self.cards = cards_repo or AsyncCardRepository(db_path)
        self.tool_gate = tool_gate

    async def create_issue(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        session_id, seat, summary = context.get("session_id"), args.get("seat"), args.get("summary")
        if not all([session_id, seat, summary]):
            return {"ok": False, "error": "Missing params"}
        import uuid

        issue_id = f"ISSUE-{str(uuid.uuid4())[:4].upper()}"
        card_data = {
            "id": issue_id,
            "session_id": session_id,
            "seat": seat,
            "summary": summary,
            "type": args.get("type", "issue"),
            "priority": args.get("priority", "Medium"),
            "status": "ready",
        }
        await self.cards.save(card_data)
        return {"ok": True, "issue_id": issue_id}

    async def update_issue_status(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        from orket.core.domain.state_machine import StateMachine, StateMachineError
        from orket.schema import CardStatus, CardType

        context = context or {}
        issue_id = args.get("issue_id") or context.get("issue_id")
        new_status_str = args.get("status", "").lower()
        if not issue_id or not new_status_str:
            return {"ok": False, "error": "Missing params"}

        try:
            new_status = CardStatus(new_status_str)
        except ValueError:
            return {"ok": False, "error": f"Invalid status: {new_status_str}"}

        issue = await self.cards.get_by_id(issue_id)
        if not issue:
            return {"ok": False, "error": f"Issue not found: {issue_id}"}

        current_status = issue.status if isinstance(issue.status, CardStatus) else CardStatus(str(issue.status))

        roles = context.get("roles")
        if roles is None:
            role = context.get("role", "")
            roles = [role] if role else []

        gate_context = {**context, "current_status": current_status.value}
        if self.tool_gate:
            gate_violation = self.tool_gate.validate(
                tool_name="update_issue_status",
                args=args,
                context=gate_context,
                roles=roles,
            )
            if gate_violation:
                return {"ok": False, "error": gate_violation}
        else:
            wait_reason = args.get("wait_reason")
            try:
                StateMachine.validate_transition(
                    card_type=CardType.ISSUE,
                    current=current_status,
                    requested=new_status,
                    roles=roles,
                    wait_reason=wait_reason,
                )
            except StateMachineError as exc:
                return {"ok": False, "error": str(exc)}

        await self.cards.update_status(issue_id, new_status)
        return {"ok": True, "issue_id": issue_id, "status": new_status.value}

    async def add_issue_comment(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        issue_id, content = context.get("issue_id"), args.get("comment")
        if not issue_id or not content:
            return {"ok": False, "error": "Missing params"}
        await self.cards.add_comment(issue_id, context.get("role", "Unknown"), content)
        return {"ok": True, "message": "Comment added."}

    async def get_issue_context(self, args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        issue_id = args.get("issue_id") or context.get("issue_id")
        if not issue_id:
            return {"ok": False, "error": "No issue_id"}
        comments = await self.cards.get_comments(issue_id)
        issue_data = await self.cards.get_by_id(issue_id)
        if issue_data is None:
            issue_payload: Dict[str, Any] = {}
        elif hasattr(issue_data, "model_dump"):
            issue_payload = issue_data.model_dump()
        elif isinstance(issue_data, dict):
            issue_payload = issue_data
        else:
            issue_payload = {
                "status": getattr(issue_data, "status", None),
                "summary": getattr(issue_data, "summary", None),
            }

        status = issue_payload.get("status")
        if hasattr(status, "value"):
            status = status.value

        return {
            "ok": True,
            "status": status,
            "summary": issue_payload.get("summary"),
            "comments": comments,
        }
