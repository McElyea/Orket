from __future__ import annotations

from collections.abc import Iterable

RUN_PHASE_SCHEMA_VERSION = "1.0"

CANONICAL_RUN_PHASE_ORDER: tuple[str, ...] = (
    "input_normalize",
    "route",
    "render_prompt",
    "execute",
    "validate",
    "repair",
    "finalize",
    "persist",
    "emit_observability",
)

_PHASE_INDEX = {phase: index for index, phase in enumerate(CANONICAL_RUN_PHASE_ORDER)}


def run_phase_contract_snapshot() -> dict[str, object]:
    return {
        "schema_version": RUN_PHASE_SCHEMA_VERSION,
        "entry_phase": CANONICAL_RUN_PHASE_ORDER[0],
        "terminal_phase": CANONICAL_RUN_PHASE_ORDER[-1],
        "canonical_phase_order": list(CANONICAL_RUN_PHASE_ORDER),
    }


def normalize_phase_trace(phases: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(phase or "").strip().lower() for phase in phases if str(phase or "").strip())
    if not normalized:
        raise ValueError("E_RUN_PHASE_TRACE_REQUIRED")
    return normalized


def validate_phase_trace(phases: Iterable[str]) -> tuple[str, ...]:
    trace = normalize_phase_trace(phases)
    previous_phase = ""
    previous_index = -1
    for phase in trace:
        index = _PHASE_INDEX.get(phase)
        if index is None:
            raise ValueError(f"E_RUN_PHASE_UNKNOWN:{phase}")
        if index < previous_index:
            raise ValueError(f"E_RUN_PHASE_ORDER:{previous_phase}->{phase}")
        previous_phase = phase
        previous_index = index
    return trace
