from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_stream_scenario import run_scenario


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


def _run_checked_scenario(path: Path, timeout_s: float) -> bool:
    verdict = run_scenario(scenario_path=path, timeout_s=timeout_s)
    return str(verdict.get("status")) == "PASS"


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
    args = parser.parse_args()

    os.environ["ORKET_MODEL_STREAM_PROVIDER"] = args.provider_mode
    root = Path(args.scenarios_root).resolve()
    scenario_names = BASELINE_SCENARIOS + PROVIDER_SCENARIOS

    if args.provider_mode == "real" and not args.skip_preflight:
        cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / "check_model_provider_preflight.py")]
        if args.preflight_smoke_stream:
            cmd.append("--smoke-stream")
        preflight = subprocess.run(cmd, cwd=PROJECT_ROOT)
        if preflight.returncode != 0:
            print("MODEL_STREAMING_GATE=FAIL")
            print("FAILURE real_provider_preflight")
            return preflight.returncode

    failures: list[str] = []
    for name in scenario_names:
        scenario_path = root / name
        if not scenario_path.exists():
            failures.append(f"{name} (missing scenario file)")
            print(f"FAIL scenario={name} reason=missing_file")
            continue
        if not _run_checked_scenario(scenario_path, timeout_s=args.timeout):
            failures.append(name)

    if failures:
        print("MODEL_STREAMING_GATE=FAIL")
        for item in failures:
            print(f"FAILURE {item}")
        return 1

    print("MODEL_STREAMING_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
