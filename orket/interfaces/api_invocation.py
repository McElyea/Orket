"""Captured API invocation and existing task bookkeeping."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any, cast

from fastapi import HTTPException

from orket.application.services import api_policy_input_service as api_policy
from orket.application.services.api_background_invocation_service import schedule_api_job


def resolve_api_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Callable[..., Any]:
    method_name = invocation["method_name"]
    method = getattr(target, method_name, None)
    if method is None or not callable(method):
        detail = invocation.get("unsupported_detail")
        if detail:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=400, detail=f"Unsupported {error_prefix} method '{method_name}'.")
    return cast(Callable[..., Any], method)


async def invoke_api_method(target: object, invocation: dict[str, Any], error_prefix: str) -> Any:
    invocation = api_policy.capture_api_invocation(invocation)
    method = resolve_api_method(target, invocation, error_prefix)
    return await method(*invocation.get("args", []), **invocation.get("kwargs", {}))


async def schedule_api_invocation_task(
    target: object,
    invocation: dict[str, Any],
    error_prefix: str,
    session_id: str,
    *, runtime_getter,
) -> None:
    invocation = api_policy.capture_api_invocation(invocation)
    method = resolve_api_method(target, invocation, error_prefix)
    context = runtime_getter()
    await schedule_api_job(context, partial(method, *invocation.get("args", []), **invocation.get("kwargs", {})), session_id)
