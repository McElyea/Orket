from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from orket.application.services.governed_agent_runtime import governed_agent_wake_view
from orket.application.services.governed_agent_scheduled_wake_service import (
    governed_agent_schedule_evaluation_view,
)
from orket.application.services.governed_agent_terminal_history import GovernedAgentTerminalHistoryConflict
from orket.application.services.governed_agent_wake_control_service import (
    governed_agent_wake_action_view,
)
from orket.application.services.governed_agent_webhook_ingress_service import (
    GOVERNED_AGENT_WEBHOOK_MAX_BODY_BYTES,
    governed_agent_webhook_delivery_view,
)


def build_governed_agents_router(
    *,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> APIRouter:
    router = APIRouter()
    _register_wake_routes(router, runtime_getter, outbound_filter)
    _register_schedule_routes(router, runtime_getter, outbound_filter)
    _register_webhook_routes(router, runtime_getter, outbound_filter)
    _register_control_routes(router, runtime_getter, outbound_filter)
    _register_run_routes(router, runtime_getter, outbound_filter)
    return router


def _register_webhook_routes(
    router: APIRouter,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> None:
    @router.post("/agent-webhooks/{issuer_ref}/deliveries/{delivery_id}", status_code=202)
    async def deliver_webhook(issuer_ref: str, delivery_id: str, request: Request) -> dict[str, Any]:
        body = await _bounded_webhook_body(request)
        try:
            result = await runtime_getter().webhook_ingress.deliver(
                issuer_ref=issuer_ref,
                delivery_id=delivery_id,
                delivered_at_utc=request.headers.get("X-Orket-Webhook-Timestamp"),
                key_id=request.headers.get("X-Orket-Webhook-Key-Id"),
                signature=request.headers.get("X-Orket-Webhook-Signature"),
                body=body,
            )
        except ValueError as exc:
            _raise_webhook_error(exc)
        response = outbound_filter(
            {
                "object_type": "governed_agent_webhook_delivery_result",
                "schema_version": "governed_agent_webhook_delivery_result.v1",
                "status": result.status,
                "delivery": governed_agent_webhook_delivery_view(result.delivery),
                "wake": None if result.wake is None else governed_agent_wake_view(result.wake),
            },
            "api.governed_agent.webhook.deliver",
        )
        if result.status == "conflict":
            raise HTTPException(status_code=409, detail=response)
        return response

    @router.get("/agent-webhooks/{issuer_ref}/deliveries")
    async def list_webhook_deliveries(issuer_ref: str) -> dict[str, Any]:
        try:
            deliveries = await runtime_getter().webhook_ingress.list_deliveries(
                issuer_ref=issuer_ref,
            )
        except ValueError as exc:
            _raise_bad_request(exc)
        return outbound_filter(
            {
                "object_type": "governed_agent_webhook_delivery_list",
                "schema_version": "governed_agent_webhook_delivery_list.v1",
                "items": [governed_agent_webhook_delivery_view(item) for item in deliveries],
            },
            "api.governed_agent.webhook.list",
        )


def _register_schedule_routes(
    router: APIRouter,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> None:
    @router.post("/agent-schedules/{schedule_id}/evaluations", status_code=202)
    async def evaluate_schedule(schedule_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().scheduled_wakes.evaluate(
                schedule_id=schedule_id,
                payload=payload,
            )
        except ValueError as exc:
            _raise_bad_request(exc)
        response = outbound_filter(
            {
                "object_type": "governed_agent_schedule_evaluation_result",
                "schema_version": "governed_agent_schedule_evaluation_result.v1",
                "status": result.status,
                "evaluation": governed_agent_schedule_evaluation_view(result.evaluation),
                "wake": None if result.wake is None else governed_agent_wake_view(result.wake),
            },
            "api.governed_agent.schedule.evaluate",
        )
        if result.status == "conflict":
            raise HTTPException(status_code=409, detail=response)
        return response

    @router.get("/agent-schedules/{schedule_id}/evaluations")
    async def list_schedule_evaluations(schedule_id: str) -> dict[str, Any]:
        try:
            evaluations = await runtime_getter().scheduled_wakes.list_evaluations(
                schedule_id=schedule_id,
            )
        except ValueError as exc:
            _raise_bad_request(exc)
        return outbound_filter(
            {
                "object_type": "governed_agent_schedule_evaluation_list",
                "schema_version": "governed_agent_schedule_evaluation_list.v1",
                "items": [governed_agent_schedule_evaluation_view(item) for item in evaluations],
            },
            "api.governed_agent.schedule.list",
        )


def _register_wake_routes(
    router: APIRouter,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> None:
    @router.get("/agent-runtime/status")
    async def runtime_status() -> dict[str, Any]:
        return outbound_filter(runtime_getter().status(), "api.governed_agent.status")

    @router.post("/agent-wakes", status_code=202)
    async def enqueue_wake(payload: dict[str, Any]) -> dict[str, Any]:
        runtime = runtime_getter()
        try:
            result = await runtime.enqueue_api_wake(payload)
        except ValueError as exc:
            _raise_bad_request(exc)
        if result.status == "conflict" or result.wake is None:
            raise HTTPException(
                status_code=409,
                detail={"ok": False, "code": "E_AGENT_WAKE_CONFLICT", "message": "Wake identity conflicts."},
            )
        return outbound_filter(
            {
                "object_type": "governed_agent_wake_admission",
                "schema_version": "governed_agent_wake_admission.v1",
                "status": result.status,
                "wake": governed_agent_wake_view(result.wake),
                "runtime": runtime.status(),
            },
            "api.governed_agent.wake.enqueue",
        )

    @router.get("/agent-wakes")
    async def list_wakes(run_id: str | None = Query(default=None)) -> dict[str, Any]:
        wakes = await runtime_getter().list_wakes(run_id=run_id)
        return outbound_filter(
            {
                "object_type": "governed_agent_wake_list",
                "schema_version": "governed_agent_wake_list.v1",
                "items": [governed_agent_wake_view(wake) for wake in wakes],
            },
            "api.governed_agent.wake.list",
        )

    @router.get("/agent-wakes/{wake_id}")
    async def get_wake(wake_id: str) -> dict[str, Any]:
        wake = await runtime_getter().get_wake(wake_id=wake_id)
        if wake is None:
            raise HTTPException(status_code=404, detail=f"Governed-agent wake '{wake_id}' not found.")
        return outbound_filter(governed_agent_wake_view(wake), "api.governed_agent.wake.get")


def _register_control_routes(
    router: APIRouter,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> None:
    @router.post("/agent-runs/{run_id}/controls")
    async def control_run(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().run_controls.request(run_id, payload)
        except ValueError as exc:
            _raise_bad_request(exc)
        response = outbound_filter(result, "api.governed_agent.run.control")
        if result["status"] in {"too_late", "conflict"}:
            raise HTTPException(status_code=409, detail=response)
        return response

    @router.post("/agent-wakes/{wake_id}/cancel")
    async def cancel_wake(wake_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().cancel_wake(wake_id=wake_id, payload=payload)
        except ValueError as exc:
            _raise_bad_request(exc)
        return _control_response(result, outbound_filter, "api.governed_agent.wake.cancel")

    @router.post("/agent-wakes/{wake_id}/recover")
    async def recover_wake(wake_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().recover_wake(wake_id=wake_id, payload=payload)
        except ValueError as exc:
            _raise_bad_request(exc)
        return _control_response(result, outbound_filter, "api.governed_agent.wake.recover")

    @router.get("/agent-wakes/{wake_id}/actions")
    async def list_wake_actions(wake_id: str) -> dict[str, Any]:
        runtime = runtime_getter()
        if await runtime.get_wake(wake_id=wake_id) is None:
            raise HTTPException(status_code=404, detail=f"Governed-agent wake '{wake_id}' not found.")
        actions = await runtime.wake_controls.list_actions(wake_id=wake_id)
        return outbound_filter(
            {
                "object_type": "governed_agent_wake_action_list",
                "schema_version": "governed_agent_wake_action_list.v1",
                "items": [governed_agent_wake_action_view(action) for action in actions],
            },
            "api.governed_agent.wake.actions",
        )


def _register_run_routes(
    router: APIRouter,
    runtime_getter: Callable[[], Any],
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
) -> None:

    @router.post("/agent-runs/{run_id}/effects/{approval_id}/resolve")
    async def resolve_effect(run_id: str, approval_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().effect_controls.apply(
                run_id=run_id,
                approval_id_ref=approval_id,
                payload=payload,
            )
        except ValueError as exc:
            _raise_bad_request(exc)
        return _effect_control_response(
            result,
            outbound_filter,
            "api.governed_agent.effect.resolve",
        )

    @router.post("/agent-runs/{run_id}/effects/resume")
    @router.post("/agent-runs/{run_id}/resume")
    async def resume_effects(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await runtime_getter().effect_controls.apply(
                run_id=run_id,
                approval_id_ref=None,
                payload=payload,
            )
        except ValueError as exc:
            _raise_bad_request(exc)
        return _effect_control_response(
            result,
            outbound_filter,
            "api.governed_agent.effect.resume",
        )

    @router.get("/agent-runs/{run_id}")
    async def inspect_run(run_id: str) -> dict[str, Any]:
        try:
            inspection = await runtime_getter().inspect(run_id=run_id)
        except GovernedAgentTerminalHistoryConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if inspection is None:
            raise HTTPException(status_code=404, detail=f"Governed-agent run '{run_id}' not found.")
        return outbound_filter(inspection, "api.governed_agent.run.inspect")

    @router.get("/agent-runs/{run_id}/replay")
    async def replay_run(run_id: str) -> dict[str, Any]:
        replay = await runtime_getter().replay(run_id=run_id)
        if replay is None:
            raise HTTPException(status_code=404, detail=f"Governed-agent run '{run_id}' not found.")
        return outbound_filter(replay, "api.governed_agent.run.replay")


def _control_response(
    result: Any,
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
    surface: str,
) -> dict[str, Any]:
    payload = outbound_filter(
        {
            "object_type": "governed_agent_wake_control_result",
            "schema_version": "governed_agent_wake_control_result.v1",
            "status": result.status,
            "wake": None if result.wake is None else governed_agent_wake_view(result.wake),
            "action": governed_agent_wake_action_view(result.action),
        },
        surface,
    )
    if result.status in {"conflict", "stale"}:
        raise HTTPException(status_code=409, detail=payload)
    return payload


def _effect_control_response(
    result: Any,
    outbound_filter: Callable[[dict[str, Any], str], dict[str, Any]],
    surface: str,
) -> dict[str, Any]:
    wake_result = result.wake
    wake = None if wake_result is None else wake_result.wake
    resolution = result.resolution
    return outbound_filter(
        {
            "object_type": "governed_agent_effect_control_result",
            "schema_version": "governed_agent_effect_control_result.v1",
            "status": result.status,
            "receipt": None if resolution is None else resolution.receipt.model_dump(mode="json"),
            "operator_action": (
                None if resolution is None else resolution.operator_action.model_dump(mode="json")
            ),
            "effect_journal_ref": None if resolution is None else resolution.effect_journal_ref,
            "accepted_checkpoint_ref": result.accepted_checkpoint_ref,
            "resume_operator_action_ref": result.resume_operator_action_ref,
            "wake_status": None if wake_result is None else wake_result.status,
            "wake": None if wake is None else governed_agent_wake_view(wake),
        },
        surface,
    )


def _raise_bad_request(exc: ValueError) -> None:
    message = str(exc or "").strip() or "Governed-agent wake admission failed."
    code = message.split(":", 1)[0]
    if not code.startswith("E_"):
        code = "E_AGENT_WAKE_INVALID"
    raise HTTPException(
        status_code=400,
        detail={"ok": False, "code": code, "message": message},
    ) from exc


def _raise_webhook_error(exc: ValueError) -> None:
    message = str(exc or "").strip() or "Webhook admission failed."
    code = message.split(":", 1)[0]
    if code == "E_AGENT_WEBHOOK_NOT_CONFIGURED":
        status_code = 503
    elif code == "E_AGENT_WEBHOOK_BODY_TOO_LARGE":
        status_code = 413
    elif code.startswith((
        "E_AGENT_WEBHOOK_ISSUER_",
        "E_AGENT_WEBHOOK_KEY_ID_",
        "E_AGENT_WEBHOOK_SIGNATURE_",
        "E_AGENT_WEBHOOK_TIMESTAMP_",
    )):
        status_code = 401
    else:
        status_code = 400
    raise HTTPException(
        status_code=status_code,
        detail={"ok": False, "code": code, "message": message},
    ) from exc


async def _bounded_webhook_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > GOVERNED_AGENT_WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail={
                    "ok": False,
                    "code": "E_AGENT_WEBHOOK_BODY_TOO_LARGE",
                    "message": "Webhook body exceeds the 1048576-byte limit.",
                },
            )
    return bytes(body)
