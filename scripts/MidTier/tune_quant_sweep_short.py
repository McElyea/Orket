from __future__ import annotations
import sys
import argparse
import copy
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
from quant_sweep.config import load_matrix_config
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run short quant-sweep probes to tune canary/task settings before a long run. "
            "Emits per-model recommended overrides."
        )
    )
    parser.add_argument("--matrix-config", required=True, help="Base matrix config JSON path.")
    parser.add_argument("--models", default="", help="Optional comma-separated model subset (defaults to matrix models order).")
    parser.add_argument("--candidate-task-ids", default="6,8,9,10", help="Comma-separated numeric task IDs to probe for canary stability.")
    parser.add_argument("--probe-quant-tag", default="Q8_0", help="Quant tag used for canary probe scoring.")
    parser.add_argument("--canary-runs", type=int, default=4, help="Canary repeats per probe candidate.")
    parser.add_argument("--probe-runs", type=int, default=1, help="Row runs per quant in probe mode (keep low for speed).")
    parser.add_argument("--summary-root", default="benchmarks/results/quant_sweep/tuning", help="Root output folder for tuning artifacts.")
    parser.add_argument("--validate-all-quants", action="store_true", help="After task-ID selection, run one short validation across all matrix quants per model.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue remaining models when one model probe fails.")
    return parser.parse_args()
def _safe_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value or "").strip())
    return token or "unknown"
def _parse_models(matrix_payload: dict[str, Any], models_raw: str) -> list[str]:
    if str(models_raw or "").strip():
        return [token.strip() for token in str(models_raw).split(",") if token.strip()]
    rows = matrix_payload.get("models")
    if not isinstance(rows, list):
        raise SystemExit("Matrix config must include a non-empty 'models' array.")
    models = [str(item).strip() for item in rows if str(item).strip()]
    if not models:
        raise SystemExit("Matrix config 'models' resolved to empty.")
    return models
def _parse_task_ids(raw: str) -> list[int]:
    resolved: list[int] = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            parsed = int(token)
        except ValueError as exc:
            raise SystemExit(f"Invalid --candidate-task-ids token '{token}'") from exc
        if parsed <= 0:
            continue
        resolved.append(parsed)
    if not resolved:
        raise SystemExit("No valid candidate task IDs provided.")
    return sorted(dict.fromkeys(resolved))
def _write_matrix(tmp_dir: Path, payload: dict[str, Any], label: str) -> Path:
    path = tmp_dir / f"{_safe_token(label)}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
def _run_command(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return int(result.returncode), str(result.stdout or ""), str(result.stderr or "")
def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Summary {path} must be a JSON object.")
    return payload
@dataclass
class ProbeScore:
    task_id: int
    passed: bool
    missing_telemetry_rate: float
    latency_variance: float | None
    overhead_ratio: float | None
    polluted_run_rate: float
    score: float
    summary_path: str
    error: str = ""
def _read_probe_score(summary: dict[str, Any], summary_path: Path, task_id: int) -> ProbeScore:
    canary = summary.get("canary") if isinstance(summary.get("canary"), dict) else {}
    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    first_session = sessions[0] if sessions and isinstance(sessions[0], dict) else {}
    per_quant = first_session.get("per_quant") if isinstance(first_session.get("per_quant"), list) else []
    first_row = per_quant[0] if per_quant and isinstance(per_quant[0], dict) else {}
    passed = bool(canary.get("passed"))
    missing_raw = canary.get("missing_telemetry_rate")
    missing = float(missing_raw) if isinstance(missing_raw, (int, float)) else 1.0
    latency_var = canary.get("internal_latency_variance")
    latency = float(latency_var) if isinstance(latency_var, (int, float)) else None
    overhead = first_row.get("orchestration_overhead_ratio")
    overhead_ratio = float(overhead) if isinstance(overhead, (int, float)) else None
    polluted_raw = first_row.get("polluted_run_rate")
    polluted = float(polluted_raw) if isinstance(polluted_raw, (int, float)) else 1.0
    score = 0.0
    if passed:
        score += 2.0
    score += max(0.0, 1.0 - missing)
    if latency is not None:
        score += max(0.0, 1.0 - min(1.0, latency))
    if overhead_ratio is not None:
        score += max(0.0, 1.0 - min(1.0, overhead_ratio))
    score += max(0.0, 1.0 - polluted)
    return ProbeScore(
        task_id=int(task_id),
        passed=passed,
        missing_telemetry_rate=round(missing, 6),
        latency_variance=round(latency, 6) if latency is not None else None,
        overhead_ratio=round(overhead_ratio, 6) if overhead_ratio is not None else None,
        polluted_run_rate=round(polluted, 6),
        score=round(score, 6),
        summary_path=str(summary_path).replace("\\", "/"),
    )
def _recommended_row_overhead_threshold(best: ProbeScore, matrix_payload: dict[str, Any]) -> float:
    base = matrix_payload.get("row_max_orchestration_overhead_ratio")
    current = float(base) if isinstance(base, (int, float)) else 0.65
    observed = best.overhead_ratio if isinstance(best.overhead_ratio, float) else current
    candidate = max(current, observed + 0.08)
    return round(min(0.95, candidate), 4)
def _build_probe_payload(
    matrix_payload: dict[str, Any],
    *,
    model_id: str,
    probe_quant_tag: str,
    task_id: int,
    canary_runs: int,
    probe_runs: int,
) -> dict[str, Any]:
    payload = copy.deepcopy(matrix_payload)
    payload["models"] = [model_id]
    payload["quants"] = [probe_quant_tag]
    payload["runs_per_quant"] = int(probe_runs)
    payload["task_limit"] = 1
    payload["task_id_min"] = int(task_id)
    payload["task_id_max"] = int(task_id)
    payload["canary_runs"] = int(canary_runs)
    payload["canary_task_limit"] = 1
    payload["canary_task_id_min"] = int(task_id)
    payload["canary_task_id_max"] = int(task_id)
    return payload
def _build_validate_payload(
    matrix_payload: dict[str, Any],
    *,
    model_id: str,
    task_id: int,
    canary_runs: int,
    probe_runs: int,
    recommended_overhead_threshold: float,
) -> dict[str, Any]:
    payload = copy.deepcopy(matrix_payload)
    payload["models"] = [model_id]
    payload["runs_per_quant"] = int(probe_runs)
    payload["task_limit"] = 1
    payload["task_id_min"] = int(task_id)
    payload["task_id_max"] = int(task_id)
    payload["canary_runs"] = int(canary_runs)
    payload["canary_task_limit"] = 1
    payload["canary_task_id_min"] = int(task_id)
    payload["canary_task_id_max"] = int(task_id)
    payload["row_max_orchestration_overhead_ratio"] = float(recommended_overhead_threshold)
    return payload
def _build_recommended_longrun_payload(
    matrix_payload: dict[str, Any],
    *,
    model_id: str,
    recommended_overrides: dict[str, Any],
) -> dict[str, Any]:
    payload = copy.deepcopy(matrix_payload)
    payload["models"] = [str(model_id)]
    for key, value in recommended_overrides.items():
        payload[str(key)] = value
    return payload
def _run_probe(
    *,
    matrix_path: Path,
    summary_path: Path,
    out_dir: Path,
) -> tuple[int, str, str]:
    cmd = [
        "python",
        "scripts/MidTier/run_quant_sweep.py",
        "--model-id",
        "placeholder",
        "--quant-tags",
        "Q8_0",
        "--matrix-config",
        str(matrix_path),
        "--summary-out",
        str(summary_path),
        "--out-dir",
        str(out_dir),
    ]
    return _run_command(cmd)
def main() -> int:
    args = _parse_args()
    matrix_payload = load_matrix_config(str(args.matrix_config))
    models = _parse_models(matrix_payload, str(args.models or ""))
    task_ids = _parse_task_ids(str(args.candidate_task_ids))
    summary_root = Path(str(args.summary_root))
    summary_root.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict[str, Any]] = []
    failed = False
    with tempfile.TemporaryDirectory(prefix="quant_sweep_tuner_") as tmp_raw:
        tmp_dir = Path(tmp_raw)
        for model_id in models:
            model_token = _safe_token(model_id)
            model_root = summary_root / model_token
            model_root.mkdir(parents=True, exist_ok=True)
            model_rows: list[ProbeScore] = []
            model_error = ""
            for task_id in task_ids:
                probe_payload = _build_probe_payload(
                    matrix_payload,
                    model_id=model_id,
                    probe_quant_tag=str(args.probe_quant_tag),
                    task_id=task_id,
                    canary_runs=int(args.canary_runs),
                    probe_runs=int(args.probe_runs),
                )
                matrix_file = _write_matrix(tmp_dir, probe_payload, f"{model_token}_task{task_id}_probe_matrix")
                summary_path = model_root / f"probe_task_{task_id}_summary.json"
                out_dir = model_root / f"probe_task_{task_id}"
                out_dir.mkdir(parents=True, exist_ok=True)
                return_code, stdout, stderr = _run_probe(
                    matrix_path=matrix_file,
                    summary_path=summary_path,
                    out_dir=out_dir,
                )
                if stdout.strip():
                    print(stdout)
                if stderr.strip():
                    print(stderr)
                if return_code != 0 or not summary_path.exists():
                    error = (
                        f"probe_failed return_code={return_code}"
                        if return_code != 0
                        else "probe_failed summary_missing"
                    )
                    model_rows.append(
                        ProbeScore(
                            task_id=task_id,
                            passed=False,
                            missing_telemetry_rate=1.0,
                            latency_variance=None,
                            overhead_ratio=None,
                            polluted_run_rate=1.0,
                            score=0.0,
                            summary_path=str(summary_path).replace("\\", "/"),
                            error=error,
                        )
                    )
                    continue
                summary_payload = _load_summary(summary_path)
                model_rows.append(_read_probe_score(summary_payload, summary_path, task_id))
            ranked = sorted(
                model_rows,
                key=lambda row: (row.passed, row.score, -row.missing_telemetry_rate),
                reverse=True,
            )
            best = ranked[0] if ranked else None
            validation_summary_path = ""
            if best and bool(args.validate_all_quants):
                overhead_threshold = _recommended_row_overhead_threshold(best, matrix_payload)
                validate_payload = _build_validate_payload(
                    matrix_payload,
                    model_id=model_id,
                    task_id=int(best.task_id),
                    canary_runs=max(2, int(args.canary_runs)),
                    probe_runs=int(args.probe_runs),
                    recommended_overhead_threshold=overhead_threshold,
                )
                validate_matrix = _write_matrix(tmp_dir, validate_payload, f"{model_token}_validate_matrix")
                validation_summary = model_root / "validation_all_quants_summary.json"
                validation_out_dir = model_root / "validation_all_quants"
                return_code, stdout, stderr = _run_probe(
                    matrix_path=validate_matrix,
                    summary_path=validation_summary,
                    out_dir=validation_out_dir,
                )
                if stdout.strip():
                    print(stdout)
                if stderr.strip():
                    print(stderr)
                if return_code == 0 and validation_summary.exists():
                    validation_summary_path = str(validation_summary).replace("\\", "/")
            recommended_overrides: dict[str, Any] = {}
            recommended_matrix_path = ""
            if best:
                recommended_overrides = {
                    "task_id_min": int(best.task_id),
                    "task_id_max": int(best.task_id),
                    "canary_task_id_min": int(best.task_id),
                    "canary_task_id_max": int(best.task_id),
                    "canary_runs": max(6, int(args.canary_runs)),
                    "canary_task_limit": 1,
                    "row_max_orchestration_overhead_ratio": _recommended_row_overhead_threshold(best, matrix_payload),
                }
                if best.missing_telemetry_rate == 0.0:
                    recommended_overrides["canary_max_missing_telemetry_rate"] = 0.1
                else:
                    recommended_overrides["canary_max_missing_telemetry_rate"] = 0.2
                recommended_payload = _build_recommended_longrun_payload(
                    matrix_payload,
                    model_id=model_id,
                    recommended_overrides=recommended_overrides,
                )
                recommended_matrix = model_root / "long_run_recommended_matrix.json"
                recommended_matrix.write_text(json.dumps(recommended_payload, indent=2) + "\n", encoding="utf-8")
                recommended_matrix_path = str(recommended_matrix).replace("\\", "/")
            else:
                failed = True
                model_error = "no_probe_results"
            if best and not best.passed:
                failed = True
                model_error = "best_probe_failed_canary"
                if not bool(args.continue_on_error):
                    manifest_rows.append(
                        {
                            "model_id": model_id,
                            "status": "FAILED",
                            "error": model_error,
                            "probe_results": [row.__dict__ for row in ranked],
                            "recommended_overrides": recommended_overrides,
                            "recommended_matrix_config": recommended_matrix_path,
                            "validation_summary": validation_summary_path,
                        }
                    )
                    break
            manifest_rows.append(
                {
                    "model_id": model_id,
                    "status": "FAILED" if model_error else "OK",
                    "error": model_error,
                    "best_task_id": int(best.task_id) if best else None,
                    "probe_results": [row.__dict__ for row in ranked],
                    "recommended_overrides": recommended_overrides,
                    "recommended_matrix_config": recommended_matrix_path,
                    "validation_summary": validation_summary_path,
                }
            )
            if model_error and not bool(args.continue_on_error):
                failed = True
                break
    manifest = {
        "schema_version": "quant_sweep.tuning.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "matrix_config": str(Path(args.matrix_config)).replace("\\", "/"),
        "models_requested": models,
        "candidate_task_ids": task_ids,
        "probe_quant_tag": str(args.probe_quant_tag),
        "canary_runs": int(args.canary_runs),
        "probe_runs": int(args.probe_runs),
        "results": manifest_rows,
        "status": "FAILED" if failed else "OK",
        "convergence": {},
    }
    manifest_path = summary_root / "tuning_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    convergence_report_path = summary_root / "convergence_report.json"
    convergence_cmd = [
        "python", "scripts/MidTier/check_quant_tuning_convergence.py",
        "--summary-root", str(summary_root), "--models", ",".join(models),
        "--out", str(convergence_report_path),
    ]
    convergence_code, convergence_stdout, convergence_stderr = _run_command(convergence_cmd)
    if convergence_stdout.strip():
        print(convergence_stdout)
    if convergence_stderr.strip():
        print(convergence_stderr)
    if convergence_code == 0 and convergence_report_path.exists():
        convergence_payload = _load_summary(convergence_report_path)
        convergence = {
            "status": "OK",
            "overall_decision": str(convergence_payload.get("overall_decision") or "UNKNOWN"),
            "report_path": str(convergence_report_path).replace("\\", "/"),
            "error": "",
        }
    else:
        convergence = {
            "status": "FAILED",
            "overall_decision": "UNKNOWN",
            "report_path": str(convergence_report_path).replace("\\", "/"),
            "error": f"convergence_check_failed return_code={convergence_code}",
        }
        failed = True
    manifest["convergence"] = convergence
    manifest["status"] = "FAILED" if failed else "OK"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(f"Convergence overall decision: {convergence.get('overall_decision')}")
    return 1 if failed else 0
if __name__ == "__main__":
    raise SystemExit(main())
