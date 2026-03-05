from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

SCRIPTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_ROOT not in sys.path:
    sys.path.insert(0, SCRIPTS_ROOT)

try:
    from scripts.providers.provider_model_resolver import choose_model, list_provider_models
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from provider_model_resolver import choose_model, list_provider_models


def _stream_smoke_ollama(*, base_url: str, model_id: str, timeout_s: float) -> tuple[bool, str]:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "stream": True,
        "options": {"num_predict": 1, "temperature": 0},
    }
    try:
        with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s)) as client:
            first_chunk = None
            with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        first_chunk = parsed
                        break
            if first_chunk is None:
                return False, "No stream chunks returned from /api/chat."
            if str(first_chunk.get("error") or "").strip():
                return False, f"Streaming call failed: {first_chunk.get('error')}"
    except httpx.HTTPStatusError as exc:
        return False, f"Streaming call failed with status={exc.response.status_code} url={base_url}/api/chat."
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        return False, f"Streaming call failed: {exc}"
    return True, ""


def _stream_smoke_openai_compat(*, base_url: str, model_id: str, timeout_s: float, api_key: str | None) -> tuple[bool, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "stream": True,
        "max_tokens": 1,
        "temperature": 0,
    }
    try:
        with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s), headers=headers) as client:
            first_chunk = None
            with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    raw = line.strip()
                    if not raw.startswith("data:"):
                        continue
                    body = raw[5:].strip()
                    if not body or body == "[DONE]":
                        continue
                    parsed = json.loads(body)
                    if isinstance(parsed, dict):
                        first_chunk = parsed
                        break
            if first_chunk is None:
                return False, "No stream chunks returned from /chat/completions."
    except httpx.HTTPStatusError as exc:
        return (
            False,
            f"Streaming call failed with status={exc.response.status_code} url={base_url}/chat/completions.",
        )
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        return False, f"Streaming call failed: {exc}"
    return True, ""


def _resolve_model_id(*, requested_model: str, models: list[str], auto_select_model: bool) -> tuple[str, str]:
    token = str(requested_model or "").strip()
    if token and token in models:
        return token, "requested"
    if token and not auto_select_model:
        return "", "missing"
    if not token and not auto_select_model:
        return "", "missing_model_id"
    resolved = choose_model(models, preferred_model=token)
    if not resolved:
        return "", "empty_registry"
    return resolved, "auto_selected"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight checks for real model streaming providers.")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["ollama", "openai_compat", "lmstudio"],
        help="Real provider to preflight (defaults to ORKET_MODEL_STREAM_REAL_PROVIDER or ollama).",
    )
    parser.add_argument("--base-url", default=None, help="Optional provider base URL override.")
    parser.add_argument("--model-id", default=None, help="Model id to validate (defaults to env).")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--auto-select-model",
        action="store_true",
        help="Auto-select a provider-compatible model when requested/default model is unavailable.",
    )
    parser.add_argument(
        "--smoke-stream",
        action="store_true",
        help="Also run a minimal streaming generation smoke check (num_predict=1).",
    )
    args = parser.parse_args()

    requested_provider = str(args.provider or os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama")).strip().lower() or "ollama"
    requested_model = str(args.model_id or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "")).strip()
    api_key = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None

    try:
        listing = list_provider_models(
            provider=requested_provider,
            base_url=args.base_url,
            timeout_s=float(args.timeout),
            api_key=api_key,
        )
    except httpx.ConnectError:
        if requested_provider in {"lmstudio", "openai_compat"}:
            print(
                "PREFLIGHT=FAIL reason=unreachable detail=OpenAI-compatible endpoint is unreachable. "
                "Start LM Studio server and verify ORKET_MODEL_STREAM_OPENAI_BASE_URL."
            )
        else:
            print(
                "PREFLIGHT=FAIL reason=unreachable detail=Ollama endpoint is unreachable. "
                "Start Ollama and verify OLLAMA_HOST."
            )
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            "PREFLIGHT=FAIL reason=http_error "
            f"detail=Provider endpoint failed with status={exc.response.status_code} url={exc.request.url}."
        )
        return 1
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"PREFLIGHT=FAIL reason=http_error detail={exc}")
        return 1

    canonical_provider = str(listing.get("canonical_provider") or "")
    base_url = str(listing.get("base_url") or "")
    models = [str(model) for model in (listing.get("models") or [])]
    auto_select_model = bool(args.auto_select_model) or not bool(requested_model)
    resolved_model, resolution_mode = _resolve_model_id(
        requested_model=requested_model,
        models=models,
        auto_select_model=auto_select_model,
    )

    if not models:
        print(
            "PREFLIGHT=FAIL reason=no_models detail=Provider model registry is empty. "
            "Load/pull at least one model and retry."
        )
        return 1

    if not resolved_model:
        available = ", ".join(models)
        if resolution_mode == "missing_model_id":
            print(
                "PREFLIGHT=FAIL reason=missing_model_id "
                "detail=Set ORKET_MODEL_STREAM_REAL_MODEL_ID or pass --model-id (or use --auto-select-model)."
            )
        else:
            print(
                f"PREFLIGHT=FAIL reason=model_missing detail=model '{requested_model}' not found. "
                f"available={available}"
            )
        return 1

    print(f"provider={requested_provider} canonical={canonical_provider} base_url={base_url} model_id={resolved_model}")
    print(f"RESOLVED_MODEL_ID={resolved_model}")
    print(f"RESOLUTION_MODE={resolution_mode}")

    if bool(args.smoke_stream):
        if canonical_provider == "openai_compat":
            ok, detail = _stream_smoke_openai_compat(
                base_url=base_url,
                model_id=resolved_model,
                timeout_s=float(args.timeout),
                api_key=api_key,
            )
        else:
            ok, detail = _stream_smoke_ollama(base_url=base_url, model_id=resolved_model, timeout_s=float(args.timeout))
        if not ok:
            print(f"PREFLIGHT=FAIL reason=streaming_failed detail={detail}")
            return 1

    print("PREFLIGHT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
