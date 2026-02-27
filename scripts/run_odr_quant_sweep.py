from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import generate_odr_role_matrix_index as odr_index
from run_arbiter import ArbiterFailure, RunArbiter


def _parse_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _slug_model(model_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(model_id or "").strip().lower())
    return cleaned.strip("_") or "model"


def _load_base_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("base spec must be a JSON object")
    config = payload.get("config")
    if isinstance(config, dict):
        return config
    return payload


def _build_command(
    *,
    python_bin: str,
    architect_model: str,
    auditor_model: str,
    out_path: Path,
    config: dict[str, Any],
) -> list[str]:
    cmd = [
        python_bin,
        "scripts/run_odr_live_role_matrix.py",
        "--architect-models",
        architect_model,
        "--auditor-models",
        auditor_model,
        "--out",
        str(out_path),
    ]

    rounds = config.get("rounds")
    if isinstance(rounds, int):
        cmd.extend(["--rounds", str(rounds)])

    scenario_ids = config.get("scenario_ids")
    if isinstance(scenario_ids, list) and scenario_ids:
        cmd.extend(["--scenario-ids", ",".join(str(item) for item in scenario_ids)])

    temperature = config.get("temperature")
    if isinstance(temperature, (int, float)):
        cmd.extend(["--temperature", str(temperature)])

    timeout = config.get("timeout")
    if isinstance(timeout, int):
        cmd.extend(["--timeout", str(timeout)])

    odr_config = config.get("odr_config")
    if isinstance(odr_config, dict):
        mapping = {
            "max_rounds": "--max-rounds",
            "diff_floor_pct": "--diff-floor-pct",
            "stable_rounds": "--stable-rounds",
            "shingle_k": "--shingle-k",
            "margin": "--margin",
            "min_loop_sim": "--min-loop-sim",
        }
        for key, flag in mapping.items():
            value = odr_config.get(key)
            if isinstance(value, (int, float)):
                cmd.extend([flag, str(value)])
        patterns = odr_config.get("code_leak_patterns")
        if isinstance(patterns, list):
            cmd.extend(["--code-leak-patterns-json", json.dumps(patterns)])

    return cmd


def run_sweep(args: argparse.Namespace) -> int:
    base_config = _load_base_config(Path(args.base_spec))
    architects = _parse_list(args.architect_models)
    if not architects:
        raise SystemExit("E_ARCHITECTS_REQUIRED provide --architect-models")

    auditors = _parse_list(args.auditor_models)
    if not auditors:
        cfg_auditors = base_config.get("auditor_models")
        if isinstance(cfg_auditors, list):
            auditors = [str(item) for item in cfg_auditors if str(item).strip()]
    if not auditors:
        raise SystemExit("E_AUDITORS_REQUIRED provide --auditor-models or base spec config.auditor_models")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index_out = Path(args.index_out)
    provenance_requested = bool(args.provenance_out.strip())
    provenance_out = Path(args.provenance_out) if provenance_requested else None
    arbiter_plan_out = Path(args.arbiter_plan_out.strip()) if args.arbiter_plan_out.strip() else out_dir / "arbiter_plan.json"
    arbiter_error_out = (
        Path(args.arbiter_error_out.strip()) if args.arbiter_error_out.strip() else out_dir / "arbiter_error.json"
    )
    arbiter = RunArbiter(plan_out=arbiter_plan_out, error_out=arbiter_error_out)
    plan = arbiter.compile_plan(
        python_bin=args.python_bin,
        base_spec=Path(args.base_spec),
        out_dir=out_dir,
        index_out=index_out,
        provenance_out=provenance_out,
        require_provenance=provenance_requested,
        require_clean_git=bool(args.require_clean_git),
        architects=architects,
        auditors=auditors,
    )
    arbiter.write_plan(plan)

    try:
        arbiter.preflight(plan)

        total = len(architects) * len(auditors)
        run_index = 0
        for architect in architects:
            for auditor in auditors:
                run_index += 1
                file_name = f"odr_live_role_matrix.{_slug_model(architect)}_{_slug_model(auditor)}.json"
                out_path = out_dir / file_name
                cmd = _build_command(
                    python_bin=args.python_bin,
                    architect_model=architect,
                    auditor_model=auditor,
                    out_path=out_path,
                    config=base_config,
                )
                print(f"[{run_index}/{total}] {architect} x {auditor}")
                result = subprocess.run(cmd, check=False)
                if result.returncode != 0:
                    raise ArbiterFailure(
                        phase="execution",
                        code="E_ARB_EXECUTION_FAILED",
                        message="ODR live matrix command failed.",
                        failures=[f"subprocess_exit:{result.returncode}"],
                        context={
                            "architect_model": architect,
                            "auditor_model": auditor,
                            "artifact": out_path.as_posix(),
                        },
                    )
                arbiter.validate_run_output(path=out_path, architect_model=architect, auditor_model=auditor)

        payload = odr_index.generate_index(input_dir=out_dir, output_path=index_out)
        print(f"Wrote {index_out} (runs={payload['run_count']})")

        if provenance_requested and provenance_out is not None:
            prov_cmd = [
                args.python_bin,
                "scripts/generate_odr_provenance.py",
                "--input-dir",
                str(out_dir),
                "--out",
                str(provenance_out),
            ]
            if args.no_provenance_probes:
                prov_cmd.append("--no-probes")
            result = subprocess.run(prov_cmd, check=False)
            if result.returncode != 0:
                raise ArbiterFailure(
                    phase="execution",
                    code="E_ARB_EXECUTION_FAILED",
                    message="ODR provenance generation failed.",
                    failures=[f"subprocess_exit:{result.returncode}"],
                    context={"artifact": provenance_out.as_posix()},
                )

        arbiter.postflight(plan)
        return 0
    except ArbiterFailure as failure:
        arbiter.emit_error_artifact(failure)
        print(f"{failure.code} {failure.message}")
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ODR live role-matrix quant/model sweep and regenerate ODR index."
    )
    parser.add_argument(
        "--base-spec",
        default="benchmarks/published/ODR/odr_live_role_matrix.qwen14b_gemma27b.json",
        help="Base config source. Accepts either full run payload (uses .config) or raw config object.",
    )
    parser.add_argument("--architect-models", required=True, help="Comma-separated architect model IDs.")
    parser.add_argument(
        "--auditor-models",
        default="",
        help="Comma-separated auditor model IDs. If omitted, uses base spec config.auditor_models.",
    )
    parser.add_argument("--out-dir", default="benchmarks/published/ODR")
    parser.add_argument("--index-out", default="benchmarks/published/ODR/index.json")
    parser.add_argument("--provenance-out", default="benchmarks/published/ODR/provenance.json")
    parser.add_argument("--no-provenance-probes", action="store_true")
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Fail arbiter preflight if git worktree is dirty.",
    )
    parser.add_argument(
        "--arbiter-plan-out",
        default="",
        help="Optional path for deterministic run plan artifact (defaults to <out-dir>/arbiter_plan.json).",
    )
    parser.add_argument(
        "--arbiter-error-out",
        default="",
        help="Optional path for deterministic arbiter error artifact (defaults to <out-dir>/arbiter_error.json).",
    )
    parser.add_argument("--python-bin", default=sys.executable)
    args = parser.parse_args()
    return run_sweep(args)


if __name__ == "__main__":
    raise SystemExit(main())
