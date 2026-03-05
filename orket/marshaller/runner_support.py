from __future__ import annotations

from typing import Any, Sequence

from .gates import GateResult


def collect_gate_rejection_codes(results: Sequence[GateResult]) -> tuple[str, ...]:
    codes: list[str] = []
    for row in results:
        if row.passed or not row.rejection_code:
            continue
        codes.append(row.rejection_code)
    return tuple(codes)


def optional_positive_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def metrics_payload(gate_results: tuple[GateResult, ...], accepted: bool) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "gate_count": len(gate_results),
        "gate_pass_count": sum(1 for row in gate_results if row.passed),
        "flake_detected": any(row.flake_detected for row in gate_results),
    }

