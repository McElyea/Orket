from __future__ import annotations

from typing import Any, Callable, Dict, List
from pathlib import Path
import uuid

from orket.decision_nodes.contracts import PlanningInput
from orket.schema import CardStatus


class DefaultPlannerNode:
    """
    Built-in planner decision node.
    Preserves existing orchestration candidate behavior.
    """

    def plan(self, data: PlanningInput) -> List[Any]:
        backlog = data.backlog
        independent_ready = data.independent_ready
        target_issue_id = data.target_issue_id

        in_review = [i for i in backlog if i.status == CardStatus.CODE_REVIEW]

        if target_issue_id:
            target = next((i for i in backlog if i.id == target_issue_id), None)
            if not target:
                return []
            if target.status == CardStatus.CODE_REVIEW:
                return [target]
            if target.status == CardStatus.READY and any(i.id == target_issue_id for i in independent_ready):
                return [target]
            return []

        return in_review + independent_ready


class DefaultRouterNode:
    """
    Built-in router decision node.
    Preserves existing seat-routing behavior, including integrity-guard preference
    during review turns.
    """

    def route(self, issue: Any, team: Any, is_review_turn: bool) -> str:
        if not is_review_turn:
            return issue.seat

        verifier_seat = next(
            (name for name, seat in team.seats.items() if "integrity_guard" in seat.roles),
            None,
        )
        return verifier_seat or issue.seat


class DefaultPromptStrategyNode:
    """
    Built-in prompt/model strategy decision node.
    Delegates to existing ModelSelector behavior to preserve runtime defaults.
    """

    def __init__(self, model_selector: Any):
        self.model_selector = model_selector

    def select_model(self, role: str, asset_config: Any) -> str:
        return self.model_selector.select(role=role, asset_config=asset_config)

    def select_dialect(self, model: str) -> str:
        return self.model_selector.get_dialect_name(model)


class DefaultEvaluatorNode:
    """
    Built-in evaluator decision node.
    Preserves existing success/failure orchestration decisions.
    """

    def evaluate_success(
        self,
        issue: Any,
        updated_issue: Any,
        turn: Any,
        seat_name: str,
        is_review_turn: bool,
    ) -> Dict[str, Any]:
        return {
            "remember_decision": ("decision" in (turn.content or "").lower()) or ("architect" in seat_name),
            "trigger_sandbox": (
                updated_issue.status == CardStatus.CODE_REVIEW
                or (updated_issue.status == issue.status and not is_review_turn)
            ),
            "promote_code_review": updated_issue.status == issue.status,
        }

    def evaluate_failure(self, issue: Any, result: Any) -> Dict[str, Any]:
        if result.violations:
            return {"action": "governance_violation", "next_retry_count": issue.retry_count}

        next_retry_count = issue.retry_count + 1
        if next_retry_count > issue.max_retries:
            return {"action": "catastrophic", "next_retry_count": next_retry_count}

        return {"action": "retry", "next_retry_count": next_retry_count}


class DefaultToolStrategyNode:
    """
    Built-in tool strategy decision node.
    Preserves the legacy static tool mapping behavior.
    """

    def compose(self, toolbox: Any) -> Dict[str, Callable]:
        return {
            "read_file": toolbox.fs.read_file,
            "write_file": toolbox.fs.write_file,
            "list_directory": toolbox.fs.list_directory,
            "image_analyze": toolbox.vision.image_analyze,
            "image_generate": toolbox.vision.image_generate,
            "create_issue": toolbox.cards.create_issue,
            "update_issue_status": toolbox.cards.update_issue_status,
            "add_issue_comment": toolbox.cards.add_issue_comment,
            "get_issue_context": toolbox.cards.get_issue_context,
            "nominate_card": toolbox.nominate_card,
            "report_credits": toolbox.report_credits,
            "refinement_proposal": toolbox.refinement_proposal,
            "request_excuse": toolbox.request_excuse,
            "archive_eval": toolbox.academy.archive_eval,
            "promote_prompt": toolbox.academy.promote_prompt,
        }


class DefaultApiRuntimeStrategyNode:
    """
    Built-in API runtime strategy node.
    Preserves existing API request/runtime decision behavior.
    """

    def parse_allowed_origins(self, origins_value: str) -> List[str]:
        return [origin.strip() for origin in origins_value.split(",") if origin.strip()]

    def resolve_asset_id(self, path: str | None, issue_id: str | None) -> str | None:
        if issue_id:
            return issue_id
        if path:
            return Path(path).stem
        return None

    def create_session_id(self) -> str:
        return str(uuid.uuid4())[:8]
