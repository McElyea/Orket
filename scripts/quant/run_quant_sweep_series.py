from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import argparse
import copy
import json
import re
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from providers.lmstudio_model_cache import LmStudioCacheClearError, clear_loaded_models, default_lmstudio_base_url
from quant_sweep.config import load_matrix_config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run quant sweep matrix one model at a time (serial), preserving shared instructions."
    )
    parser.add_argument("--matrix-config", required=True, help="Path to quant sweep matrix config JSON.")
    parser.add_argument(
        "--models",
        default="",
        help="Optional comma-separated model override subset. Defaults to matrix models order.",
    )
    parser.add_argument(
        "--summary-root",
        default="benchmarks/results/quant/quant_sweep/series",
        help="Directory for per-model summaries and run artifacts.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining models even if one run fails.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned per-model commands and exit without executing.",
    )
    parser.add_argument(
        "--sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_true",
        default=True,
        help="Unload all LM Studio model instances before and after the series run (default: enabled).",
    )
    parser.add_argument(
        "--no-sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_false",
        help="Skip LM Studio model-cache sanitation.",
    )
    parser.add_argument(
        "--lmstudio-base-url",
        default=default_lmstudio_base_url(),
        help=(
            "LM Studio server base URL. Accepts root or suffixed URLs (for example /v1 or /api/v1). "
            "Used only for sanitation calls."
        ),
    )
    parser.add_argument(
        "--lmstudio-timeout-sec",
        type=int,
        default=10,
        help="Timeout in seconds for LM Studio sanitation endpoint calls.",
    )
    return parser.parse_args()


def _safe_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
    return token or "unknown_model"


def _resolve_models(matrix_payload: dict[str, Any], models_override: str) -> list[str]:
    if str(models_override or "").strip():
        return [token.strip() for token in str(models_override).split(",") if token.strip()]
    models = matrix_payload.get("models")
    if not isinstance(models, list):
        raise SystemExit("Matrix config must define a non-empty 'models' array.")
    resolved = [str(token).strip() for token in models if str(token).strip()]
    if not resolved:
        raise SystemExit("Matrix config 'models' resolved to empty.")
    return resolved


def _build_model_matrix_payload(matrix_payload: dict[str, Any], model_id: str) -> dict[str, Any]:
    single = copy.deepcopy(matrix_payload)
    single["models"] = [str(model_id)]
    return single


def _write_temp_matrix(payload: dict[str, Any], model_id: str, tmp_dir: Path) -> Path:
    path = tmp_dir / f"{_safe_token(model_id)}_matrix.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return int(result.returncode), str(result.stdout or ""), str(result.stderr or "")


def main() -> int:
    args = _parse_args()
    matrix_path = Path(str(args.matrix_config))
    matrix_payload = load_matrix_config(str(matrix_path))
    models = _resolve_models(matrix_payload, str(args.models or ""))

    summary_root = Path(str(args.summary_root))
    summary_root.mkdir(parents=True, exist_ok=True)

    plan_rows: list[dict[str, Any]] = []
    for model_id in models:
        model_token = _safe_token(model_id)
        plan_rows.append(
            {
                "model_id": model_id,
                "summary_out": str((summary_root / f"{model_token}_summary.json")).replace("\\", "/"),
                "out_dir": str((summary_root / model_token)).replace("\\", "/"),
            }
        )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "status": "DRY_RUN",
                    "matrix_config": str(matrix_path).replace("\\", "/"),
                    "models": models,
                    "plan": plan_rows,
                    "model_cache_sanitation": {
                        "enabled": bool(args.sanitize_model_cache),
                        "lmstudio_base_url": str(args.lmstudio_base_url),
                        "timeout_sec": int(args.lmstudio_timeout_sec),
                    },
                },
                indent=2,
            )
        )
        return 0

    started = time.perf_counter()
    executed: list[dict[str, Any]] = []
    failed = False
    sanitation_events: list[dict[str, Any]] = []
    post_sanitation_error = ""

    if bool(args.sanitize_model_cache):
        try:
            sanitation_events.append(
                clear_loaded_models(
                    stage="pre_run",
                    base_url=str(args.lmstudio_base_url),
                    timeout_sec=int(args.lmstudio_timeout_sec),
                    strict=True,
                )
            )
        except LmStudioCacheClearError as exc:
            raise SystemExit(str(exc)) from exc

    try:
        with tempfile.TemporaryDirectory(prefix="quant_sweep_series_") as tmp_raw:
            tmp_dir = Path(tmp_raw)
            for row in plan_rows:
                model_id = str(row["model_id"])
                summary_out = Path(str(row["summary_out"]))
                out_dir = Path(str(row["out_dir"]))
                out_dir.mkdir(parents=True, exist_ok=True)
                summary_out.parent.mkdir(parents=True, exist_ok=True)

                single_payload = _build_model_matrix_payload(matrix_payload, model_id)
                matrix_file = _write_temp_matrix(single_payload, model_id, tmp_dir)
                cmd = [
                    "python",
                    "scripts/quant/run_quant_sweep.py",
                    "--model-id",
                    "placeholder",
                    "--quant-tags",
                    "Q8_0",
                    "--matrix-config",
                    str(matrix_file),
                    "--summary-out",
                    str(summary_out),
                    "--out-dir",
                    str(out_dir),
                ]
                return_code, stdout, stderr = _run(cmd)
                executed.append(
                    {
                        "model_id": model_id,
                        "return_code": return_code,
                        "summary_out": str(summary_out).replace("\\", "/"),
                        "out_dir": str(out_dir).replace("\\", "/"),
                    }
                )
                if stdout.strip():
                    print(stdout)
                if stderr.strip():
                    print(stderr)
                if return_code != 0:
                    failed = True
                    if not bool(args.continue_on_error):
                        break
    finally:
        if bool(args.sanitize_model_cache):
            try:
                sanitation_events.append(
                    clear_loaded_models(
                        stage="post_run",
                        base_url=str(args.lmstudio_base_url),
                        timeout_sec=int(args.lmstudio_timeout_sec),
                        strict=True,
                    )
                )
            except LmStudioCacheClearError as exc:
                if isinstance(exc.result, dict) and exc.result:
                    sanitation_events.append(exc.result)
                post_sanitation_error = str(exc)
                failed = True

    manifest = {
        "schema_version": "quant_sweep.series.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "matrix_config": str(matrix_path).replace("\\", "/"),
        "models_requested": models,
        "results": executed,
        "status": "FAILED" if failed else "OK",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "model_cache_sanitation": {
            "enabled": bool(args.sanitize_model_cache),
            "lmstudio_base_url": str(args.lmstudio_base_url),
            "timeout_sec": int(args.lmstudio_timeout_sec),
            "events": sanitation_events,
            "post_run_error": post_sanitation_error,
        },
    }
    manifest_path = summary_root / "series_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    if post_sanitation_error:
        print(post_sanitation_error)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
