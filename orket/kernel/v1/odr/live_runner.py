from __future__ import annotations

from typing import Any

from .core import ReactorConfig, ReactorState, run_round
from .prompt_contract import build_architect_messages, build_auditor_messages


def _response_content(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("content") or "").strip()
    return str(getattr(response, "content", "") or "").strip()


async def run_live_refinement(
    *,
    task: str,
    architect_client: Any,
    auditor_client: Any,
    max_rounds: int = 8,
    max_attempts: int | None = None,
) -> dict[str, Any]:
    state = ReactorState()
    current_requirement = str(task or "").strip()
    prior_auditor_output = ""
    rounds: list[dict[str, Any]] = []
    attempt_budget = int(max_attempts if max_attempts is not None else max_rounds)
    cfg = ReactorConfig(max_attempts=attempt_budget)

    for round_index in range(1, attempt_budget + 1):
        architect_messages = build_architect_messages(
            task=str(task),
            current_requirement=current_requirement,
            prior_auditor_output=prior_auditor_output,
        )
        architect_raw = _response_content(await architect_client.complete(architect_messages))

        auditor_messages = build_auditor_messages(task=str(task), architect_output=architect_raw)
        auditor_raw = _response_content(await auditor_client.complete(auditor_messages))

        prior_count = len(state.history_rounds)
        state = run_round(state, architect_raw, auditor_raw, cfg)
        trace = state.history_rounds[-1] if len(state.history_rounds) > prior_count else None
        if isinstance(trace, dict) and str(trace.get("validity_verdict") or "") == "valid":
            architect_parsed = trace.get("architect_parsed")
            if isinstance(architect_parsed, dict):
                next_requirement = str(architect_parsed.get("requirement") or "").strip()
                if next_requirement:
                    current_requirement = next_requirement

        prior_auditor_output = auditor_raw
        rounds.append(
            {
                "round": round_index,
                "architect_raw": architect_raw,
                "auditor_raw": auditor_raw,
                "trace": trace,
                "state_stop_reason_after_round": state.stop_reason,
            }
        )
        if state.stop_reason is not None:
            break

    final_trace = state.history_rounds[-1] if state.history_rounds else {}
    final_requirement = ""
    if isinstance(final_trace, dict):
        architect_parsed = final_trace.get("architect_parsed")
        if isinstance(architect_parsed, dict):
            final_requirement = str(architect_parsed.get("requirement") or "").strip()
    if not final_requirement:
        final_requirement = current_requirement

    stop_reason = str(state.stop_reason or "")
    validity_verdict = str(final_trace.get("validity_verdict") or "invalid") if isinstance(final_trace, dict) else "invalid"
    odr_valid = validity_verdict == "valid"
    if stop_reason in {"CODE_LEAK", "FORMAT_VIOLATION"}:
        odr_failure_mode: str | None = stop_reason.lower()
    elif not odr_valid:
        odr_failure_mode = "semantic_invalid"
    else:
        odr_failure_mode = None
    return {
        "task": str(task),
        "rounds": rounds,
        "rounds_completed": len(state.history_rounds),
        "stop_reason": stop_reason or None,
        "history_v": list(state.history_v),
        "valid_history_v": list(state.valid_history_v),
        "history_rounds": list(state.history_rounds),
        "final_requirement": final_requirement,
        "final_trace": final_trace,
        "odr_valid": odr_valid,
        "odr_failure_mode": odr_failure_mode,
        "odr_pending_decisions": int(final_trace.get("pending_decision_count") or 0)
        if isinstance(final_trace, dict)
        else 0,
        "odr_stop_reason": stop_reason or None,
    }
