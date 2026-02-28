from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASELINE_SCENARIOS = [
    "s0_unknown_workload_400.yaml",
    "s5_backpressure_drop_ranges.yaml",
    "s6_finalize_cancel_noop.yaml",
]

PROVIDER_SCENARIOS = [
    "s7_real_model_happy_path.yaml",
    "s8_real_model_cancel_mid_gen.yaml",
    "s9_real_model_cold_load_visibility.yaml",
]


def _run_checked_scenario(path: Path, timeout_s: float, *, gate_run_id: str, loop_index: int) -> bool:
    scenario_name = path.name.lower()
    direct_provider_scenario = scenario_name in {
        "s7_real_model_happy_path.yaml",
        "s8_real_model_cancel_mid_gen.yaml",
        "s9_real_model_cold_load_visibility.yaml",
    } and str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "")).strip().lower() == "real"
    module_name = "scripts.run_provider_scenario_direct" if direct_provider_scenario else "scripts.run_stream_scenario"
    cmd = [
        sys.executable,
        "-m",
        module_name,
        "--scenario",
        str(path),
        "--timeout",
        str(timeout_s),
    ]
    env = dict(os.environ)
    env["ORKET_STREAM_GATE_RUN_ID"] = gate_run_id
    env["ORKET_STREAM_GATE_LOOP_INDEX"] = str(loop_index)
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return proc.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run model-streaming acceptance gate scenarios.")
    parser.add_argument(
        "--scenarios-root",
        default="docs/observability/stream_scenarios",
        help="Directory containing model-streaming scenario YAML files.",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-scenario timeout in seconds.")
    parser.add_argument(
        "--provider-mode",
        default="stub",
        choices=["stub", "real"],
        help="Provider mode for provider-enabled scenarios.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip real-provider preflight checks.",
    )
    parser.add_argument(
        "--preflight-smoke-stream",
        action="store_true",
        help="Include a minimal real streaming smoke check during real-provider preflight.",
    )
    parser.add_argument(
        "--real-provider",
        default=None,
        choices=["ollama", "openai_compat", "lmstudio"],
        help="Real provider backend to use when --provider-mode real.",
    )
    parser.add_argument(
        "--stability-loops",
        type=int,
        default=1,
        help="Run the full gate this many times and fail fast on first failing loop.",
    )
    args = parser.parse_args()

    os.environ["ORKET_MODEL_STREAM_PROVIDER"] = args.provider_mode
    if args.provider_mode == "real" and args.real_provider:
        os.environ["ORKET_MODEL_STREAM_REAL_PROVIDER"] = args.real_provider
    root = Path(args.scenarios_root).resolve()
    scenario_names = BASELINE_SCENARIOS + PROVIDER_SCENARIOS
    stability_loops = max(1, int(args.stability_loops))
    gate_run_id = f"gate-{uuid4().hex[:12]}"

    if args.provider_mode == "real" and not args.skip_preflight:
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "check_model_provider_preflight.py")]
        if args.real_provider:
            cmd.extend(["--provider", args.real_provider])
        if args.preflight_smoke_stream:
            cmd.append("--smoke-stream")
        preflight = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if preflight.returncode != 0:
            print("MODEL_STREAMING_GATE=FAIL")
            print("FAILURE real_provider_preflight")
            return preflight.returncode

    failures: list[str] = []
    for loop_index in range(1, stability_loops + 1):
        print(f"STABILITY_LOOP={loop_index}/{stability_loops} gate_run_id={gate_run_id}")
        for name in scenario_names:
            scenario_path = root / name
            if not scenario_path.exists():
                failures.append(f"loop={loop_index}:{name} (missing scenario file)")
                print(f"FAIL scenario={name} loop={loop_index} reason=missing_file")
                continue
            if not _run_checked_scenario(
                scenario_path,
                timeout_s=args.timeout,
                gate_run_id=gate_run_id,
                loop_index=loop_index,
            ):
                failures.append(f"loop={loop_index}:{name}")
                break
        if failures:
            break

    if failures:
        print("MODEL_STREAMING_GATE=FAIL")
        for item in failures:
            print(f"FAILURE {item}")
        return 1

    print(f"GATE_RUN_ID={gate_run_id}")
    print("MODEL_STREAMING_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
