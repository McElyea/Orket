from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.adapters.tools.families import (
    AcademyTools,
    CardManagementTools,
    FileSystemTools,
    GovernanceTools,
)
from orket.adapters.tools.runtime import ToolRuntimeExecutor
from orket.application.services.card_completion_service import CardCompletionService
from orket.application.services.card_completion_turn_service import (
    refresh_card_completion_request,
    verify_card_completion_claims,
)
from orket.application.services.card_workspace_mutation_service import CardWorkspaceMutationService
from orket.application.services.decision_node_registry import DecisionNodeRegistry, build_decision_node_registry
from orket.application.services.reforger_service import ReforgerService
from orket.application.services.tool_composition_service import select_tool_bindings
from orket.application.services.vision_service import VisionService
from orket.core.contracts.card_completion_commit import CardCompletionRejected, is_card_completion_call
from orket.core.domain.execution import ExecutionTurn
from orket.runtime_paths import resolve_runtime_db_path
from orket.settings import get_setting

if TYPE_CHECKING:
    from orket.adapters.storage.async_card_repository import AsyncCardRepository
    from orket.core.policies.tool_gate import ToolGateValidator as ToolGate
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
        card_completion: CardCompletionService | None = None,
    ) -> None:
        self.root = Path(workspace_root).absolute()
        self.refs = [Path(r).absolute() for r in references]
        self.db_path = resolve_runtime_db_path(db_path)
        self.organization = organization
        self.card_completion = card_completion
        self.decision_nodes = decision_nodes if decision_nodes is not None else build_decision_node_registry()
        self.tool_strategy_node = self.decision_nodes.resolve_tool_strategy(self.organization)
        self.runtime_executor = runtime_executor or ToolRuntimeExecutor()
        self.vision = VisionService(self.root, tuple(self.refs), get_setting("sd_model", "runwayml/stable-diffusion-v1-5"))
        self.cards = CardManagementTools(
            self.root,
            self.refs,
            db_path=self.db_path,
            cards_repo=cards_repo,
            tool_gate=tool_gate,
        )
        self.workspace_mutations = CardWorkspaceMutationService(self.cards.cards)
        self.fs = FileSystemTools(self.root, self.refs, mutation_authority=self.workspace_mutations)
        self.governance = GovernanceTools(self.root, self.refs, cards=self.cards)
        self.academy = AcademyTools(self.root, self.refs)
        self.reforger = ReforgerService(self.root, self.refs)

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if tool_name == "image_generate":
            args = deepcopy(args)
        tool_map = get_tool_map(self)
        if tool_name not in tool_map:
            return {"ok": False, "error": f"Unknown tool '{tool_name}'"}

        tool_fn = tool_map[tool_name]
        resolved_context = dict(context or {})
        if self.card_completion is not None and is_card_completion_call(tool_name, args):
            try:
                await refresh_card_completion_request(
                    service=self.card_completion, cards=self.cards.cards, context=resolved_context,
                )
            except CardCompletionRejected as exc:
                return {"ok": False, "error": str(exc), "error_code": "card_completion_rejected"}
        return await self.runtime_executor.invoke(
            tool_fn,
            args,
            context=resolved_context,
            tool_name=tool_name,
            tool_timeout_seconds=_resolve_tool_timeout_seconds(resolved_context),
            workspace=self.root,
            mutation_authority=self.workspace_mutations if tool_fn in (
                self.vision.image_generate, self.academy.archive_eval, self.academy.promote_prompt,
                self.reforger.inspect, self.reforger.run,
            ) else None,
        )

    async def verify_completion_claims(self, turn: ExecutionTurn, context: dict[str, Any]) -> None:
        await verify_card_completion_claims(cards=self.cards.cards, turn=turn, context=context)

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
    return select_tool_bindings(toolbox, toolbox.tool_strategy_node)


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
