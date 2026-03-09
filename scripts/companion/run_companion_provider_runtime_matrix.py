from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_csv_tokens(raw: str) -> list[str]:
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


def _score_latency(latency_ms: int) -> float:
    if latency_ms <= 800:
        return 1.0
    if latency_ms <= 1500:
        return 0.8
    if latency_ms <= 2500:
        return 0.6
    if latency_ms <= 5000:
        return 0.4
    return 0.2


def _score_mode_adherence(message: str) -> float:
    if "MATRIX_OK" in str(message or ""):
        return 1.0
    if message:
        return 0.5
    return 0.0


def _build_case_result(
    *,
    provider: str,
    model: str,
    path: str,
    result: str,
    response_payload: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    payload = dict(response_payload or {})
    latency_ms = int(payload.get("latency_ms") or 0)
    message = str(payload.get("message") or "")
    if result != "success":
        return {
            "provider": provider,
            "model": model,
            "observed_path": path,
            "result": result,
            "error": error,
            "scores": {
                "reasoning": {"status": "not_measured", "value": None},
                "conversational_quality": {"status": "not_measured", "value": None},
                "memory_usefulness": {"status": "not_measured", "value": None},
                "latency": {"status": "not_measured", "value": None},
                "footprint": {"status": "not_measured", "value": None},
                "voice_suitability": {"status": "not_measured", "value": None},
                "stability": {"status": "measured", "value": 0.0},
                "mode_adherence": {"status": "not_measured", "value": None},
            },
        }

    return {
        "provider": provider,
        "model": model,
        "observed_path": path,
        "result": result,
        "latency_ms": latency_ms,
        "message_preview": message[:160],
        "scores": {
            "reasoning": {"status": "not_measured", "value": None},
            "conversational_quality": {"status": "measured", "value": _score_mode_adherence(message)},
            "memory_usefulness": {"status": "not_measured", "value": None},
            "latency": {"status": "measured", "value": _score_latency(latency_ms)},
            "footprint": {"status": "not_measured", "value": None},
            "voice_suitability": {"status": "not_measured", "value": None},
            "stability": {"status": "measured", "value": 1.0},
            "mode_adherence": {"status": "measured", "value": _score_mode_adherence(message)},
        },
    }


def _invoke_case(
    *,
    client: httpx.Client,
    session_id: str,
    provider: str,
    model: str,
) -> dict[str, Any]:
    config_payload = {
        "session_id": session_id,
        "scope": "next_turn",
        "patch": {
            "mode": {"role_id": "general_assistant", "relationship_style": "platonic"},
            "memory": {"session_memory_enabled": True, "profile_memory_enabled": True},
        },
    }
    try:
        config_response = client.patch("/api/v1/companion/config", json=config_payload)
        config_response.raise_for_status()
        chat_response = client.post(
            "/api/v1/companion/chat",
            json={
                "session_id": session_id,
                "message": f"[{provider}:{model}] Reply with exactly: MATRIX_OK",
                "provider": provider,
                "model": model,
            },
        )
        chat_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = f"status={exc.response.status_code} url={exc.request.url}"
        return _build_case_result(
            provider=provider,
            model=model,
            path="blocked",
            result="failure",
            error=detail,
        )
    except httpx.HTTPError as exc:
        return _build_case_result(
            provider=provider,
            model=model,
            path="blocked",
            result="failure",
            error=str(exc),
        )

    payload = chat_response.json()
    return _build_case_result(
        provider=provider,
        model=model,
        path="primary",
        result="success",
        response_payload=payload,
    )


def run_companion_provider_runtime_matrix(
    *,
    base_url: str,
    api_key: str,
    providers: list[str],
    models: list[str],
    session_id: str,
    timeout_s: float,
    output_path: Path,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    timeout = max(1.0, float(timeout_s))

    cases: list[dict[str, Any]] = []
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport) as client:
        for index, provider in enumerate(providers):
            model = models[index] if index < len(models) else ""
            cases.append(
                _invoke_case(
                    client=client,
                    session_id=f"{session_id}-{provider}-{index + 1}",
                    provider=provider,
                    model=model,
                )
            )

    failures = [row for row in cases if row.get("result") != "success"]
    status = "complete" if not failures else "partial"
    payload = {
        "generated_at_utc": _now_utc_iso(),
        "status": status,
        "observed_result": "success" if not failures else "partial success",
        "providers_requested": providers,
        "models_requested": models,
        "cases": cases,
        "blockers": [
            {
                "provider": str(row.get("provider") or ""),
                "model": str(row.get("model") or ""),
                "error": str(row.get("error") or ""),
            }
            for row in failures
        ],
    }
    return write_payload_with_diff_ledger(output_path, payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Companion provider/runtime matrix checks through public host API seams.",
    )
    parser.add_argument("--base-url", default=os.getenv("COMPANION_HOST_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("ORKET_API_KEY", ""))
    parser.add_argument("--providers", default="ollama,lmstudio")
    parser.add_argument("--models", default="")
    parser.add_argument("--session-id", default="companion-matrix")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument(
        "--output",
        default="benchmarks/results/companion/provider_runtime_matrix/companion_provider_runtime_matrix.json",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    providers = _parse_csv_tokens(args.providers)
    if not providers:
        raise SystemExit("E_COMPANION_MATRIX_PROVIDERS_REQUIRED")
    models = _parse_csv_tokens(args.models)

    payload = run_companion_provider_runtime_matrix(
        base_url=str(args.base_url),
        api_key=str(args.api_key),
        providers=providers,
        models=models,
        session_id=str(args.session_id),
        timeout_s=float(args.timeout_s),
        output_path=Path(args.output),
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"status={payload.get('status')} output={args.output}")
    return 0 if str(payload.get("status") or "") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
