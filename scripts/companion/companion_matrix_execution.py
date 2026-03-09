from __future__ import annotations

from typing import Any

import httpx

from scripts.companion.companion_matrix_http_steps import (
    apply_base_config,
    apply_mode_probe_config,
    chat,
    request_json,
    stable_chat_probe,
    voice_probe,
)
from scripts.companion.companion_matrix_scoring import (
    DIMENSIONS,
    measured,
    not_measured,
    score_conversational_quality,
    score_footprint,
    score_latency,
    score_memory_usefulness,
    score_mode_adherence,
    score_reasoning,
    score_stability,
    score_voice_suitability,
)


def empty_scores() -> dict[str, dict[str, Any]]:
    return {dimension: not_measured(detail="not-collected") for dimension in DIMENSIONS}


def build_blocker(
    *,
    provider: str,
    model: str,
    step: str,
    error: str,
    observed_path: str,
    category: str = "runtime",
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model": model,
        "step": step,
        "observed_path": observed_path,
        "category": category,
        "error": str(error or ""),
    }


def _build_failure_case(
    *,
    provider: str,
    model: str,
    step: str,
    error: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case = {
        "provider": provider,
        "model": model,
        "observed_path": "blocked",
        "result": "failure",
        "failed_step": step,
        "error": str(error),
        "scores": {
            **empty_scores(),
            "stability": measured(0.0, detail="blocked-before-stability"),
        },
    }
    blockers = [
        build_blocker(
            provider=provider,
            model=model,
            step=step,
            error=error,
            observed_path="blocked",
        )
    ]
    return case, blockers


def _run_required_chat(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
    message: str,
    step: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return (
            chat(
                client=client,
                session_id=session_id,
                provider=provider,
                model=model,
                message=message,
            ),
            None,
        )
    except RuntimeError as exc:
        return None, f"{step}:{exc}"


def _collect_core_chat_evidence(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
) -> tuple[dict[str, str], list[int], str | None]:
    messages: dict[str, str] = {}
    latencies: list[int] = []
    reasoning, reasoning_error = _run_required_chat(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
        message="Compute 17 * 19 and include only the final numeric answer.",
        step="chat_reasoning",
    )
    if reasoning_error:
        return messages, latencies, reasoning_error
    reasoning_payload = reasoning or {}
    messages["reasoning"] = str(reasoning_payload.get("message") or "")
    latencies.append(int(reasoning_payload.get("latency_ms") or 0))

    try:
        apply_mode_probe_config(client=client, session_id=session_id)
    except RuntimeError as exc:
        return messages, latencies, f"config_mode_probe:{exc}"

    mode_payload, mode_error = _run_required_chat(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
        message="Start with 'Tutor:' and include the token MODE_OK.",
        step="chat_mode",
    )
    if mode_error:
        return messages, latencies, mode_error
    mode_row = mode_payload or {}
    messages["mode"] = str(mode_row.get("message") or "")
    latencies.append(int(mode_row.get("latency_ms") or 0))

    conversational, conversational_error = _run_required_chat(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
        message="A user says they feel overwhelmed. Respond in 2-3 sentences with empathy and one practical next step.",
        step="chat_conversation",
    )
    if conversational_error:
        return messages, latencies, conversational_error
    conversational_row = conversational or {}
    messages["conversational"] = str(conversational_row.get("message") or "")
    latencies.append(int(conversational_row.get("latency_ms") or 0))
    return messages, latencies, None


def _collect_memory_recall(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
) -> tuple[str | None, int, str, str | None]:
    memory_model = model.replace(":", "-").replace(" ", "-")
    memory_token = f"matrix-memory-{provider}-{memory_model}".lower()
    try:
        chat(
            client=client,
            session_id=session_id,
            provider=provider,
            model=model,
            message=f"Remember this for later: favorite_color={memory_token}.",
        )
        payload = chat(
            client=client,
            session_id=session_id,
            provider=provider,
            model=model,
            message="What favorite_color did I ask you to remember?",
        )
    except RuntimeError as exc:
        return None, 0, memory_token, f"chat_memory:{exc}"
    return str(payload.get("message") or ""), int(payload.get("latency_ms") or 0), memory_token, None


def _build_success_case(
    *,
    provider: str,
    model: str,
    stt_available: bool,
    messages: dict[str, str],
    memory_token: str,
    stable_successes: int,
    stability_attempts: int,
    latencies: list[int],
    voice_total: int,
    voice_ok: int,
    case_blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    if voice_total > 0:
        voice_score = measured(
            score_voice_suitability(
                transitions_total=voice_total,
                transitions_ok=voice_ok,
                stt_available=stt_available,
            ),
            detail=f"transitions_ok={voice_ok}/{voice_total} stt_available={stt_available}",
        )
    else:
        voice_score = not_measured(detail="voice-probe-unavailable")

    return {
        "provider": provider,
        "model": model,
        "observed_path": "degraded" if case_blockers else "primary",
        "result": "success",
        "latency_ms": avg_latency,
        "message_preview": str(messages.get("conversational") or "")[:160],
        "stt_available": stt_available,
        "scores": {
            "reasoning": measured(score_reasoning(messages.get("reasoning", ""))),
            "conversational_quality": measured(score_conversational_quality(messages.get("conversational", ""))),
            "memory_usefulness": measured(score_memory_usefulness(messages.get("memory_recall", ""), expected_token=memory_token)),
            "latency": measured(score_latency(avg_latency), detail=f"avg_latency_ms={avg_latency}"),
            "footprint": score_footprint(model),
            "voice_suitability": voice_score,
            "stability": measured(
                score_stability(successes=stable_successes, attempts=max(1, int(stability_attempts))),
                detail=f"successes={stable_successes} attempts={max(1, int(stability_attempts))}",
            ),
            "mode_adherence": measured(score_mode_adherence(messages.get("mode", ""))),
        },
    }


def evaluate_case(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
    stability_attempts: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        status_payload = request_json(client=client, method="GET", path="/api/v1/companion/status")
    except RuntimeError as exc:
        return _build_failure_case(provider=provider, model=model, step="status", error=str(exc))

    stt_available = bool(status_payload.get("stt_available"))
    try:
        apply_base_config(client=client, session_id=session_id)
    except RuntimeError as exc:
        return _build_failure_case(provider=provider, model=model, step="config_base", error=str(exc))

    messages, latencies, core_error = _collect_core_chat_evidence(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
    )
    if core_error:
        step, detail = core_error.split(":", 1)
        return _build_failure_case(provider=provider, model=model, step=step, error=detail)

    memory_text, memory_latency, memory_token, memory_error = _collect_memory_recall(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
    )
    if memory_error:
        step, detail = memory_error.split(":", 1)
        return _build_failure_case(provider=provider, model=model, step=step, error=detail)
    messages["memory_recall"] = str(memory_text or "")
    latencies.append(memory_latency)

    case_blockers: list[dict[str, Any]] = []
    stable_successes, stable_latencies, stable_failures = stable_chat_probe(
        client=client,
        session_id=session_id,
        provider=provider,
        model=model,
        attempts=stability_attempts,
    )
    latencies.extend(stable_latencies)
    if stable_successes == 0:
        return _build_failure_case(provider=provider, model=model, step="chat_stability", error="all-stability-probes-failed")
    if stable_failures:
        case_blockers.append(
            build_blocker(
                provider=provider,
                model=model,
                step="chat_stability",
                error="; ".join(stable_failures[:3]),
                observed_path="degraded",
            )
        )

    voice_total, voice_ok, voice_failures = voice_probe(client=client)
    if voice_failures:
        case_blockers.append(
            build_blocker(
                provider=provider,
                model=model,
                step="voice_probe",
                error="; ".join(voice_failures[:3]),
                observed_path="degraded",
            )
        )

    case = _build_success_case(
        provider=provider,
        model=model,
        stt_available=stt_available,
        messages=messages,
        memory_token=memory_token,
        stable_successes=stable_successes,
        stability_attempts=stability_attempts,
        latencies=latencies,
        voice_total=voice_total,
        voice_ok=voice_ok,
        case_blockers=case_blockers,
    )
    return case, case_blockers


def coverage_blockers(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for row in cases:
        if str(row.get("result") or "") != "success":
            continue
        scores = dict(row.get("scores") or {})
        missing = [
            dimension
            for dimension in DIMENSIONS
            if str((scores.get(dimension) or {}).get("status") or "") != "measured"
        ]
        if not missing:
            continue
        blockers.append(
            build_blocker(
                provider=str(row.get("provider") or ""),
                model=str(row.get("model") or ""),
                step="coverage_dimensions",
                error=f"not_measured={','.join(missing)}",
                observed_path="degraded",
                category="coverage",
            )
        )
    return blockers
