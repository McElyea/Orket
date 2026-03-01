from __future__ import annotations

from typing import Any

from orket.rulesim.workload import run_rulesim_v0 as _run_rulesim_v0
from orket.rulesim.workload import validate_rulesim_v0_start as _validate_rulesim_v0_start
from orket.streaming.manager import InteractionContext


async def run_rulesim_v0(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    return await _run_rulesim_v0(
        input_config=input_config,
        turn_params=turn_params,
        interaction_context=interaction_context,
    )


def validate_rulesim_v0_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    _validate_rulesim_v0_start(input_config=input_config, turn_params=turn_params)
