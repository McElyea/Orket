from __future__ import annotations

from collections import Counter
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


def build_run_summary(
    *,
    run_id: str,
    attempts: Sequence[Any],
    max_attempts: int,
    total_proposals_received: int,
    duration_ms: int,
) -> dict[str, Any]:
    accepted_attempt_index = next((row.attempt_index for row in attempts if row.accept), None)
    rejection_codes = [row.primary_rejection_code for row in attempts if row.primary_rejection_code]
    histogram = Counter(rejection_codes)
    return {
        "summary_contract_version": "marshaller.summary.v0",
        "run_id": run_id,
        "attempt_count": len(attempts),
        "max_attempts": max_attempts,
        "total_proposals_received": total_proposals_received,
        "accepted": accepted_attempt_index is not None,
        "accepted_attempt_index": accepted_attempt_index,
        "attempts_to_green": accepted_attempt_index,
        "time_to_green_ms": duration_ms if accepted_attempt_index is not None else None,
        "duration_ms": duration_ms,
        "primary_rejection_histogram": dict(sorted(histogram.items())),
    }


def build_triage_payload(
    *,
    run_id: str,
    attempts: Sequence[Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in attempts:
        items.append(
            {
                "attempt_index": row.attempt_index,
                "accept": row.accept,
                "primary_rejection_code": row.primary_rejection_code,
                "rejection_codes": list(row.rejection_codes),
                "decision_path": row.decision_path,
            }
        )
    items.sort(key=lambda row: row["attempt_index"])
    return {
        "triage_contract_version": "marshaller.triage.v0",
        "run_id": run_id,
        "attempts": items,
    }
