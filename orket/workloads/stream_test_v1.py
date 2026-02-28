from __future__ import annotations

from typing import Any

from orket.streaming.contracts import CommitIntent, StreamEventType
from orket.streaming.manager import InteractionContext


def _int_value(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else minimum


def _deterministic_chunk(seed: int, index: int, chunk_size: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    start = (seed + index) % len(alphabet)
    chars = []
    for offset in range(chunk_size):
        chars.append(alphabet[(start + offset) % len(alphabet)])
    return "".join(chars)


async def run_stream_test_v1(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    seed = _int_value(input_config.get("seed"), 0)
    mode = str(input_config.get("mode") or turn_params.get("mode") or "basic").strip().lower()
    workload_ref = "stream_test_v1"

    await interaction_context.emit_event(
        StreamEventType.MODEL_SELECTED,
        {"model_id": "stream-test-v1", "reason": mode, "authoritative": False},
    )

    cold_load = bool(input_config.get("force_cold_model_load"))
    await interaction_context.emit_event(
        StreamEventType.MODEL_LOADING,
        {"cold_start": cold_load, "progress": 0.0 if cold_load else 1.0, "authoritative": False},
    )
    await interaction_context.emit_event(
        StreamEventType.MODEL_READY,
        {
            "model_id": "stream-test-v1",
            "warm_state": "cold" if cold_load else "warm",
            "load_ms": 120 if cold_load else 0,
            "authoritative": False,
        },
    )

    if mode == "spam_deltas":
        delta_count = _int_value(input_config.get("delta_count"), 512, minimum=1)
        chunk_size = _int_value(input_config.get("chunk_size"), 2, minimum=1)
        for index in range(delta_count):
            await interaction_context.emit_event(
                StreamEventType.TOKEN_DELTA,
                {
                    "delta": _deterministic_chunk(seed, index, chunk_size),
                    "index": index,
                    "authoritative": False,
                },
            )
    else:
        await interaction_context.emit_event(
            StreamEventType.TOKEN_DELTA,
            {"delta": _deterministic_chunk(seed, 0, 4), "index": 0, "authoritative": False},
        )

    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref=workload_ref))
    wait_ms = _int_value(input_config.get("wait_ms"), 40, minimum=0) if mode == "finalize_then_wait" else 0
    return {"post_finalize_wait_ms": wait_ms}
