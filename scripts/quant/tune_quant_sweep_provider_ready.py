from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from providers.provider_model_resolver import choose_model, list_provider_models, normalize_provider, rank_models


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description=(
            "Provider-aware wrapper for tune_quant_sweep_short.py. "
            "Resolves provider-compatible model IDs (Ollama vs LM Studio/OpenAI-compatible) "
            "and injects runtime_env into a temporary matrix config."
        )
    )
    parser.add_argument("--matrix-config", required=True, help="Base matrix config JSON path.")
    parser.add_argument(
        "--provider",
        default=os.getenv("ORKET_LLM_PROVIDER") or os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER") or "lmstudio",
        choices=["ollama", "openai_compat", "lmstudio"],
        help="Provider backend used for model discovery and runtime_env wiring.",
    )
    parser.add_argument("--base-url", default="", help="Optional provider base URL override.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Provider model-list timeout seconds.")
    parser.add_argument(
        "--models",
        default="",
        help="Optional comma-separated explicit model IDs. If empty, models are resolved from provider.",
    )
    parser.add_argument(
        "--preferred-model",
        default=os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", ""),
        help="Preferred model for auto-selection ordering.",
    )
    parser.add_argument(
        "--auto-model-count",
        type=int,
        default=1,
        help="When --models is omitted, pick top N provider-compatible models (default 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved provider/model wiring and exit without running tuner.",
    )
    return parser.parse_known_args()


def _parse_csv_models(raw: str) -> list[str]:
    return [token.strip() for token in str(raw or "").split(",") if token.strip()]


def _load_matrix(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected top-level JSON object")
    return payload


def _resolve_models(args: argparse.Namespace) -> tuple[list[str], dict[str, object]]:
    explicit = _parse_csv_models(str(args.models or ""))
    api_key = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None
    listing = list_provider_models(
        provider=str(args.provider),
        base_url=str(args.base_url or ""),
        timeout_s=float(args.timeout),
        api_key=api_key,
    )
    provider_models = [str(model) for model in (listing.get("models") or [])]
    if explicit:
        missing = [model for model in explicit if model not in provider_models]
        if missing:
            joined = ", ".join(missing)
            raise SystemExit(
                f"Provider/model mismatch: requested models are not available from {args.provider}: {joined}"
            )
        return explicit, listing

    ranked = rank_models(provider_models, preferred_model=str(args.preferred_model or ""))
    if not ranked:
        raise SystemExit("Provider model registry returned no models.")
    count = max(1, int(args.auto_model_count))
    if count == 1:
        return [choose_model(ranked, preferred_model=str(args.preferred_model or ""))], listing
    return ranked[:count], listing


def _build_runtime_env(*, provider: str, canonical_provider: str, base_url: str) -> dict[str, str]:
    runtime_env: dict[str, str] = {}
    runtime_env["ORKET_LLM_PROVIDER"] = str(provider)
    if canonical_provider == "openai_compat":
        runtime_env["ORKET_MODEL_STREAM_OPENAI_BASE_URL"] = str(base_url)
    elif canonical_provider == "ollama":
        runtime_env["OLLAMA_HOST"] = str(base_url)
    return runtime_env


def main() -> int:
    args, passthrough = _parse_args()
    matrix_path = Path(str(args.matrix_config))
    if not matrix_path.exists():
        raise SystemExit(f"Matrix config not found: {matrix_path}")

    try:
        models, listing = _resolve_models(args)
    except httpx.ConnectError:
        raise SystemExit(f"Failed to connect to provider '{args.provider}'.")
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"Provider endpoint error status={exc.response.status_code} url={exc.request.url}")
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Provider resolution failed: {exc}")

    requested_provider = str(listing.get("requested_provider") or args.provider)
    canonical_provider = str(listing.get("canonical_provider") or normalize_provider(requested_provider))
    resolved_base_url = str(listing.get("base_url") or "")
    matrix_payload = _load_matrix(matrix_path)
    runtime_env = matrix_payload.get("runtime_env") if isinstance(matrix_payload.get("runtime_env"), dict) else {}
    merged_runtime_env = dict(runtime_env)
    merged_runtime_env.update(
        _build_runtime_env(provider=requested_provider, canonical_provider=canonical_provider, base_url=resolved_base_url)
    )
    matrix_payload["runtime_env"] = merged_runtime_env
    matrix_payload["models"] = models

    preview = {
        "provider": requested_provider,
        "canonical_provider": canonical_provider,
        "base_url": resolved_base_url,
        "models": models,
        "matrix_config_in": str(matrix_path).replace("\\", "/"),
        "pass_through_args": passthrough,
    }
    print(json.dumps(preview, indent=2))
    if bool(args.dry_run):
        return 0

    with tempfile.TemporaryDirectory(prefix="quant_tuner_provider_ready_") as tmp_dir:
        tmp_matrix = Path(tmp_dir) / "matrix.provider_ready.json"
        tmp_matrix.write_text(json.dumps(matrix_payload, indent=2) + "\n", encoding="utf-8")
        cmd = [
            sys.executable,
            "scripts/quant/tune_quant_sweep_short.py",
            "--matrix-config",
            str(tmp_matrix),
            "--models",
            ",".join(models),
            *passthrough,
        ]
        env = dict(os.environ)
        env.setdefault("ORKET_MODEL_STREAM_REAL_PROVIDER", str(requested_provider))
        if models:
            env.setdefault("ORKET_MODEL_STREAM_REAL_MODEL_ID", str(models[0]))
        result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parents[2]), env=env, check=False)
        return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
