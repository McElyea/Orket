from __future__ import annotations

from typing import Any

from orket.streaming.manager import InteractionContext

from .model_stream_v1 import run_model_stream_v1
from .stream_test_v1 import run_stream_test_v1


async def run_builtin_workload(
    *,
    workload_id: str,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    normalized = str(workload_id or "").strip()
    if normalized == "stream_test_v1":
        return await run_stream_test_v1(
            input_config=input_config,
            turn_params=turn_params,
            interaction_context=interaction_context,
        )
    if normalized == "model_stream_v1":
        return await run_model_stream_v1(
            input_config=input_config,
            turn_params=turn_params,
            interaction_context=interaction_context,
        )
    raise ValueError(f"Unknown workload '{workload_id}'")


def is_builtin_workload(workload_id: str) -> bool:
    return str(workload_id or "").strip() in {"stream_test_v1", "model_stream_v1"}
