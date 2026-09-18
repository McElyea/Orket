"""Application composition and admission for the bounded flow authoring surface."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_flow_repository import AsyncFlowRepository
from orket.application.services.flow_authoring_service import (
    FlowAuthoringService,
    FlowRunAccepted,
    FlowRuntimeNotAdmittedError,
)
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.exceptions import CardNotFound


def build_flow_authoring_service(project_root: Path, runtime_inputs: RuntimeInputService) -> FlowAuthoringService:
    return FlowAuthoringService(
        flow_repo=AsyncFlowRepository(project_root / ".orket" / "durable" / "db" / "orket_ui_flows.sqlite3"),
        now_iso_factory=runtime_inputs.utc_now_iso,
        flow_id_factory=runtime_inputs.create_flow_id,
        revision_id_factory=runtime_inputs.create_flow_revision_id,
    )


async def accept_flow_run(
    *,
    service: FlowAuthoringService,
    engine: Any,
    flow_id: str,
    expected_revision_id: str | None,
    runtime_inputs: RuntimeInputService,
    schedule: Callable[[object, dict[str, Any], str, str], Awaitable[None]],
) -> FlowRunAccepted:
    revision_id, assigned_card_id = await service.prepare_flow_run(
        flow_id=flow_id, expected_revision_id=expected_revision_id,
    )
    if await engine.cards.get_by_id(assigned_card_id) is None:
        raise FlowRuntimeNotAdmittedError("current_flow_run_slice_requires_assigned_card_present_on_host_card_surface")
    try:
        target_kind, _parent_epic_name = await engine.resolve_run_card_target(assigned_card_id)
    except CardNotFound as exc:
        raise FlowRuntimeNotAdmittedError(
            "current_flow_run_slice_requires_assigned_card_resolve_on_canonical_run_card_surface",
        ) from exc
    if target_kind != "issue":
        raise FlowRuntimeNotAdmittedError("current_flow_run_slice_requires_assigned_card_resolve_to_issue_runtime_target")
    session_id = runtime_inputs.create_session_id()
    await schedule(
        engine, {"method_name": "run_issue", "args": [assigned_card_id], "kwargs": {"session_id": session_id}},
        "run", session_id,
    )
    return FlowRunAccepted(
        flow_id=flow_id, revision_id=revision_id, session_id=session_id,
        accepted_at=runtime_inputs.utc_now_iso(),
        summary="Accepted through the bounded single-card flow run surface.",
    )
