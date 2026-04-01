from __future__ import annotations

from typing import Any

import httpx


def request_json(
    *,
    client: httpx.Client,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        response = client.request(method=method, url=path, json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = str(exc.response.text or "").strip()[:240]
        except (TypeError, ValueError, AttributeError):
            detail = ""
        raise RuntimeError(f"status={exc.response.status_code} url={exc.request.url} detail={detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(str(exc)) from exc

    decoded = response.json()
    if not isinstance(decoded, dict):
        raise RuntimeError(f"E_COMPANION_MATRIX_INVALID_RESPONSE path={path}")
    return decoded


def chat(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
    message: str,
) -> dict[str, Any]:
    return request_json(
        client=client,
        method="POST",
        path="/api/chat",
        payload={
            "session_id": session_id,
            "message": message,
            "provider": provider,
            "model": model,
        },
    )


def apply_base_config(*, client: httpx.Client, session_id: str) -> dict[str, Any]:
    return request_json(
        client=client,
        method="PATCH",
        path="/api/config",
        payload={
            "session_id": session_id,
            "scope": "next_turn",
            "patch": {
                "mode": {"role_id": "general_assistant", "relationship_style": "platonic"},
                "memory": {"session_memory_enabled": True, "profile_memory_enabled": True},
                "voice": {"silence_delay_sec": 1.0},
            },
        },
    )


def apply_mode_probe_config(*, client: httpx.Client, session_id: str) -> dict[str, Any]:
    return request_json(
        client=client,
        method="PATCH",
        path="/api/config",
        payload={
            "session_id": session_id,
            "scope": "next_turn",
            "patch": {"mode": {"role_id": "tutor", "relationship_style": "platonic"}},
        },
    )


def stable_chat_probe(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
    attempts: int,
) -> tuple[int, list[int], list[str]]:
    success_count = 0
    latencies: list[int] = []
    failures: list[str] = []
    total_attempts = max(1, int(attempts))
    for index in range(total_attempts):
        try:
            payload = chat(
                client=client,
                session_id=session_id,
                provider=provider,
                model=model,
                message=f"Reply with MATRIX_STABLE_{index + 1}.",
            )
            success_count += 1
            latencies.append(int(payload.get("latency_ms") or 0))
        except RuntimeError as exc:
            failures.append(str(exc))
    return success_count, latencies, failures


def voice_probe(*, client: httpx.Client) -> tuple[int, int, list[str]]:
    transitions_total = 0
    transitions_ok = 0
    failures: list[str] = []
    transitions = [
        ("start", "listening"),
        ("stop", "idle"),
        ("start", "listening"),
        ("submit", "processing"),
    ]
    for command, expected_state in transitions:
        transitions_total += 1
        try:
            payload = request_json(
                client=client,
                method="POST",
                path="/api/voice/control",
                payload={"command": command, "silence_delay_sec": 1.0},
            )
        except RuntimeError as exc:
            failures.append(f"voice_control:{command}:{exc}")
            continue
        observed = str(payload.get("state") or "").strip().lower()
        if observed == expected_state:
            transitions_ok += 1
        else:
            failures.append(f"voice_control:{command}:state={observed}")
    return transitions_total, transitions_ok, failures
