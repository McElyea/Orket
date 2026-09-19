"""Application interpretation of supplied run evidence and card runtime intent."""
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from orket.application.services.operator_completion_service import operator_verification
from orket.core.cards_runtime_contract import ODR_EXECUTION_PROFILE, resolve_cards_runtime


def inspect_operator_card_runtime(payload: dict[str, Any]) -> dict[str, Any]:
    captured = deepcopy(payload)
    return resolve_cards_runtime(issue=SimpleNamespace(seat=str(captured.get("seat") or "").strip(),
                                                      params=captured.get("params")))


def classify_operator_run(*, summary: dict[str, Any], status: str | None,
                          completion: dict[str, Any]) -> dict[str, Any]:
    captured = deepcopy(summary)
    raw_status = str(status or "").strip() or str(captured.get("status") or "").strip()
    runtime = captured.get("cards_runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    packet = captured.get("truthful_runtime_packet1")
    provenance = packet.get("provenance") if isinstance(packet, dict) else None
    provenance = provenance if isinstance(provenance, dict) else {}
    execution_profile = str(captured.get("execution_profile") or "").strip() or str(runtime.get("execution_profile") or "").strip()
    stop_reason = str(captured.get("stop_reason") or "").strip() or str(runtime.get("stop_reason") or "").strip()
    failure_reason = str(captured.get("failure_reason") or "").strip()
    resolution = str(captured.get("cards_runtime_resolution_state") or "").strip() or str(runtime.get("resolution_state") or "").strip()
    verification = operator_verification(deepcopy(completion))
    degraded = bool(captured.get("is_degraded")) or str(provenance.get("truth_classification") or "").strip() == "degraded"
    reasons = list(verification["reason_codes"])
    if resolution and resolution != "resolved":
        degraded = True
        reasons.append(f"cards_runtime.{resolution}")
    if stop_reason:
        reasons.append(f"run.stop_reason.{stop_reason.lower()}")
    if failure_reason:
        reasons.append(f"run.failure_reason.{failure_reason.lower()}")
    odr = execution_profile == ODR_EXECUTION_PROFILE or bool(captured.get("odr_active")) or bool(runtime.get("odr_active"))
    output_kind = str(provenance.get("primary_output_kind") or "").strip() or "none"
    primary, lifecycle = _lifecycle(raw_status.lower(), prebuild=odr and output_kind == "none",
                                     degraded=degraded, verified=verification["status"] == "verified")
    if lifecycle:
        reasons.insert(0, f"run.lifecycle.{lifecycle}")
    reason_codes = list(dict.fromkeys(str(value or "").strip() for value in reasons if str(value or "").strip()))
    return {"raw_status": raw_status or "unknown", "primary_status": primary, "degraded": degraded,
            "reason_codes": reason_codes, "lifecycle_category": lifecycle or None,
            "execution_profile": execution_profile or None, "stop_reason": stop_reason or None,
            "failure_reason": failure_reason or None, "verification": verification}


def _lifecycle(status: str, *, prebuild: bool, degraded: bool, verified: bool) -> tuple[str, str]:
    if status in {"failed", "terminal_failure"}:
        return ("blocked", "prebuild_blocked") if prebuild else ("failed", "artifact_run_failed")
    if status in {"done", "completed"}:
        category = "degraded_completed" if degraded else (
            "artifact_run_verified" if verified else "artifact_run_completed_unverified")
        return "completed", category
    if status in {"started", "in_progress", "executing"}:
        return "running", ""
    if status == "incomplete":
        return "open", ""
    if status in {"canceled", "cancelled", "operator_blocked"}:
        return "blocked", ""
    return status or "unknown", ""
