"""Owned asynchronous Kernel approval observations and resolution publication."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_invocation_service import invoke_kernel, own_kernel_publication
from orket.kernel.v1.nervous_system_runtime_extensions import decide_approval_v1, get_approval_v1, list_approvals_v1

EnrichApproval = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


async def list_kernel_approvals(*, enrich: EnrichApproval, **filters: Any) -> list[dict[str, Any]]:
    items = await invoke_kernel(list_approvals_v1, **filters)
    return [await enrich(item) for item in items]


async def get_kernel_approval(approval_id: str, *, enrich: EnrichApproval) -> dict[str, Any] | None:
    approval = await invoke_kernel(get_approval_v1, approval_id)
    return None if approval is None else await enrich(approval)


async def decide_kernel_approval(
    *,
    approval_id: str,
    decision: str,
    edited_proposal: dict[str, Any] | None,
    notes: str | None,
    operator_actor_ref: str | None,
    enrich: EnrichApproval,
    publish: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    captured = capture_kernel_request(
        dict(
            approval_id=approval_id,
            decision=decision,
            edited_proposal=edited_proposal,
            notes=notes,
            operator_actor_ref=operator_actor_ref,
        )
    )

    async def operation() -> dict[str, Any]:
        previous = await get_kernel_approval(captured["approval_id"], enrich=enrich)
        result = await invoke_kernel(
            decide_approval_v1, **{key: value for key, value in captured.items() if key != "operator_actor_ref"}
        )
        await publish(previous=previous, result=result, operator_actor_ref=captured["operator_actor_ref"])
        approval = result.get("approval")
        if isinstance(approval, dict):
            result["approval"] = await enrich(approval)
        return result

    return await own_kernel_publication(operation)
