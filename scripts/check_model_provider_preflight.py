from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx


def _resolve_base_url() -> str:
    raw = str(os.getenv("OLLAMA_HOST", "")).strip()
    if not raw:
        return "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid OLLAMA_HOST '{raw}'")
    return f"{parsed.scheme}://{parsed.netloc}"


def _extract_model_names(payload: dict[str, Any]) -> set[str]:
    models = payload.get("models")
    if not isinstance(models, list):
        return set()
    names: set[str] = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        model = str(item.get("model") or "").strip()
        if name:
            names.add(name)
        if model:
            names.add(model)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight checks for real model streaming provider (Ollama).")
    parser.add_argument("--model-id", default=None, help="Model id to validate (defaults to env or qwen2.5-coder:7b).")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--smoke-stream",
        action="store_true",
        help="Also run a minimal streaming generation smoke check (num_predict=1).",
    )
    args = parser.parse_args()

    model_id = str(args.model_id or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "qwen2.5-coder:7b")).strip()
    if not model_id:
        print("PREFLIGHT=FAIL reason=missing_model_id detail=Set ORKET_MODEL_STREAM_REAL_MODEL_ID or pass --model-id.")
        return 1

    try:
        base_url = _resolve_base_url()
    except ValueError as exc:
        print(f"PREFLIGHT=FAIL reason=invalid_host detail={exc}")
        return 1

    print(f"provider=ollama base_url={base_url} model_id={model_id}")
    try:
        with httpx.Client(base_url=base_url, timeout=max(1.0, args.timeout)) as client:
            tags_resp = client.get("/api/tags")
            tags_resp.raise_for_status()
            payload = tags_resp.json() if isinstance(tags_resp.json(), dict) else {}
    except httpx.ConnectError:
        print(
            f"PREFLIGHT=FAIL reason=unreachable detail=Ollama not reachable at {base_url}. "
            f"Start Ollama and verify OLLAMA_HOST."
        )
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"PREFLIGHT=FAIL reason=http_error detail=Ollama tags endpoint failed with "
            f"status={exc.response.status_code} url={base_url}/api/tags."
        )
        return 1
    except httpx.HTTPError as exc:
        print(f"PREFLIGHT=FAIL reason=http_error detail={exc}")
        return 1
    except ValueError:
        print("PREFLIGHT=FAIL reason=bad_json detail=Ollama /api/tags returned non-JSON response.")
        return 1

    model_names = _extract_model_names(payload)
    if model_id not in model_names:
        listed = ", ".join(sorted(model_names)) if model_names else "(none)"
        print(
            f"PREFLIGHT=FAIL reason=model_missing detail=model '{model_id}' not found. "
            f"Run: ollama pull {model_id}. available={listed}"
        )
        return 1

    if args.smoke_stream:
        stream_payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "stream": True,
            "options": {"num_predict": 1, "temperature": 0},
        }
        try:
            with httpx.Client(base_url=base_url, timeout=max(1.0, args.timeout)) as client:
                first_chunk = None
                with client.stream("POST", "/api/chat", json=stream_payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        parsed = json.loads(line)
                        if isinstance(parsed, dict):
                            first_chunk = parsed
                            break
                if first_chunk is None:
                    print("PREFLIGHT=FAIL reason=streaming_failed detail=No stream chunks returned from /api/chat.")
                    return 1
                if str(first_chunk.get("error") or "").strip():
                    print(
                        "PREFLIGHT=FAIL reason=streaming_failed "
                        f"detail=Streaming call failed: {first_chunk.get('error')}"
                    )
                    return 1
        except httpx.HTTPStatusError as exc:
            print(
                "PREFLIGHT=FAIL reason=streaming_failed "
                f"detail=Streaming call failed with status={exc.response.status_code} url={base_url}/api/chat."
            )
            return 1
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            print(f"PREFLIGHT=FAIL reason=streaming_failed detail=Streaming call failed: {exc}")
            return 1

    print("PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
