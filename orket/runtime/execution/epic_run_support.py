from __future__ import annotations

from typing import Any

from orket.exceptions import OrketInfrastructureError
from orket.runtime.epic_run_types import EpicRunCallbacks, EpicRunContext
from orket.schema import CardStatus

WORKFLOW_TERMINAL_STATUSES = {
    CardStatus.DONE,
    CardStatus.CANCELED,
    CardStatus.ARCHIVED,
    CardStatus.BLOCKED,
    CardStatus.GUARD_REJECTED,
    CardStatus.GUARD_APPROVED,
}
SUCCESS_STATUSES = {CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED}


def build_legacy_transcript(transcript: list[Any]) -> list[dict[str, Any]]:
    return [
        {"step_index": index, "role": turn.role, "issue": turn.issue_id, "summary": turn.content, "note": turn.note}
        for index, turn in enumerate(transcript)
    ]


def build_base_run_artifacts(*, callbacks: EpicRunCallbacks, context: EpicRunContext) -> dict[str, Any]:
    artifacts = dict(callbacks.run_artifact_refs(context.setup.run_id))
    artifacts.update(dict(context.run_contract_artifacts))
    artifacts["deterministic_mode_contract"] = dict(context.deterministic_mode_contract)
    artifacts["route_decision_artifact"] = dict(context.route_decision_artifact)
    artifacts["packet1_facts"] = callbacks.build_packet1_facts(intended_model=context.setup.env.model)
    return artifacts


def set_control_plane_artifacts(
    artifacts: dict[str, Any],
    *,
    control_plane_run: Any,
    control_plane_attempt: Any,
    control_plane_step: Any,
    control_plane_checkpoint: Any | None = None,
    control_plane_checkpoint_acceptance: Any | None = None,
) -> None:
    artifacts["control_plane_run_record"] = control_plane_run.model_dump(mode="json")
    artifacts["control_plane_attempt_record"] = control_plane_attempt.model_dump(mode="json")
    artifacts["control_plane_step_record"] = control_plane_step.model_dump(mode="json")
    if control_plane_checkpoint is not None:
        artifacts["control_plane_checkpoint_record"] = control_plane_checkpoint.model_dump(mode="json")
    if control_plane_checkpoint_acceptance is not None:
        artifacts["control_plane_checkpoint_acceptance_record"] = control_plane_checkpoint_acceptance.model_dump(
            mode="json"
        )


async def await_infrastructure(operation: str, awaitable: Any) -> Any:
    try:
        return await awaitable
    except (RuntimeError, OSError, TimeoutError) as exc:
        raise OrketInfrastructureError(f"{operation}: {exc}") from exc
