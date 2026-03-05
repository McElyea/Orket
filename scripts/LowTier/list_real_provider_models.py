from __future__ import annotations

import argparse
import json
import os
from typing import Any
from urllib.parse import urlparse

import httpx


def _normalize_base_url(raw: str, *, default: str) -> str:
    value = str(raw or "").strip() or default
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base URL '{value}'")
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    return f"{base}{path}" if path else base


def _list_openai_compat_models(base_url: str, api_key: str | None, timeout_s: float) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s), headers=headers) as client:
        resp = client.get("/models")
        resp.raise_for_status()
        payload = resp.json() if isinstance(resp.json(), dict) else {}
    data = payload.get("data")
    model_ids: list[str] = []
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if model_id:
                model_ids.append(model_id)
    return sorted(set(model_ids))


def _list_ollama_models(base_url: str, timeout_s: float) -> list[str]:
    with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s)) as client:
        resp = client.get("/api/tags")
        resp.raise_for_status()
        payload = resp.json() if isinstance(resp.json(), dict) else {}
    models = payload.get("models")
    ids: list[str] = []
    if isinstance(models, list):
        for row in models:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            model = str(row.get("model") or "").strip()
            if name:
                ids.append(name)
            if model:
                ids.append(model)
    return sorted(set(ids))


def main() -> int:
    parser = argparse.ArgumentParser(description="List model IDs available from configured real provider endpoints.")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["lmstudio", "openai_compat", "ollama"],
        help="Provider backend (defaults to ORKET_MODEL_STREAM_REAL_PROVIDER or lmstudio).",
    )
    parser.add_argument("--base-url", default=None, help="Override provider base URL.")
    parser.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    provider = str(args.provider or os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "lmstudio")).strip().lower()
    if provider == "lmstudio":
        provider = "openai_compat"

    try:
        if provider == "openai_compat":
            default_url = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1"))
            base_url = _normalize_base_url(args.base_url or default_url, default=default_url)
            api_key = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None
            model_ids = _list_openai_compat_models(base_url=base_url, api_key=api_key, timeout_s=args.timeout)
        elif provider == "ollama":
            default_url = str(os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
            base_url = _normalize_base_url(args.base_url or default_url, default=default_url)
            model_ids = _list_ollama_models(base_url=base_url, timeout_s=args.timeout)
        else:
            print(f"Unsupported provider '{provider}'.")
            return 1
    except httpx.ConnectError:
        print(f"Failed to connect to {provider} at {base_url}.")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Provider endpoint error status={exc.response.status_code} url={exc.request.url}")
        return 1
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"Provider query failed: {exc}")
        return 1

    if args.json:
        print(
            json.dumps(
                {"provider": provider, "base_url": base_url, "count": len(model_ids), "models": model_ids},
                indent=2,
            )
        )
        return 0

    print(f"provider={provider} base_url={base_url} count={len(model_ids)}")
    for model_id in model_ids:
        print(model_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
