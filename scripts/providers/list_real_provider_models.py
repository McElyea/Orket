from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPTS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPTS_ROOT not in sys.path:
    sys.path.insert(0, SCRIPTS_ROOT)

import httpx

try:
    from scripts.providers.provider_model_resolver import choose_model, list_provider_models
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from provider_model_resolver import choose_model, list_provider_models


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
    parser.add_argument(
        "--preferred-model",
        default="",
        help="Optional preferred model id used when emitting a recommendation.",
    )
    parser.add_argument(
        "--recommend-model",
        action="store_true",
        help="Emit a recommended provider-compatible model id.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    provider = str(args.provider or os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "lmstudio")).strip().lower() or "lmstudio"
    preferred_model = str(args.preferred_model or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "")).strip()
    try:
        api_key = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None
        listing = list_provider_models(
            provider=provider,
            base_url=args.base_url,
            timeout_s=float(args.timeout),
            api_key=api_key,
        )
        requested_provider = str(listing.get("requested_provider") or provider)
        canonical_provider = str(listing.get("canonical_provider") or "")
        base_url = str(listing.get("base_url") or "")
        model_ids = [str(model) for model in (listing.get("models") or [])]
        recommended_model = choose_model(model_ids, preferred_model=preferred_model) if bool(args.recommend_model) else ""
    except httpx.ConnectError:
        print(f"Failed to connect to {provider}.")
        return 1
    except httpx.HTTPStatusError as exc:
        print(f"Provider endpoint error status={exc.response.status_code} url={exc.request.url}")
        return 1
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        print(f"Provider query failed: {exc}")
        return 1

    if args.json:
        payload = {
            "provider": requested_provider,
            "canonical_provider": canonical_provider,
            "base_url": base_url,
            "count": len(model_ids),
            "models": model_ids,
        }
        if args.recommend_model:
            payload["preferred_model"] = preferred_model
            payload["recommended_model"] = recommended_model
        print(json.dumps(payload, indent=2))
        return 0

    print(f"provider={requested_provider} canonical={canonical_provider} base_url={base_url} count={len(model_ids)}")
    if args.recommend_model:
        print(f"recommended_model={recommended_model or '(none)'} preferred={preferred_model or '(unset)'}")
    for model_id in model_ids:
        print(model_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
