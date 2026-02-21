from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate context profile policy defaults and matrix references.")
    parser.add_argument("--profiles", default="benchmarks/configs/context_sweep_profiles.json")
    parser.add_argument(
        "--matrix-configs",
        default="benchmarks/configs/quant_sweep_common_sessions.json,benchmarks/configs/quant_sweep_logic_only.json,benchmarks/configs/quant_sweep_refactor_heavy.json,benchmarks/configs/quant_sweep_mixed.json",
    )
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def main() -> int:
    args = _parse_args()
    failures: list[str] = []
    profiles_payload = _load(Path(args.profiles))
    profiles = profiles_payload.get("profiles") if isinstance(profiles_payload.get("profiles"), dict) else {}
    for required in ("safe", "balanced", "stress"):
        if required not in profiles:
            failures.append(f"MISSING_PROFILE:{required}")
    if failures:
        print(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
        return 2

    safe = profiles["safe"]
    balanced = profiles["balanced"]
    stress = profiles["stress"]
    for name, profile in [("safe", safe), ("balanced", balanced), ("stress", stress)]:
        contexts = profile.get("contexts")
        if not isinstance(contexts, list) or not contexts:
            failures.append(f"{name}:INVALID_CONTEXTS")
        if isinstance(contexts, list) and contexts != sorted(contexts):
            failures.append(f"{name}:CONTEXTS_NOT_SORTED")
        for key in ("adherence_min", "ttft_ceiling_ms", "decode_floor_tps"):
            if not isinstance(profile.get(key), (int, float)):
                failures.append(f"{name}:MISSING_{key.upper()}")

    if float(safe.get("adherence_min", 0.0)) < float(balanced.get("adherence_min", 0.0)):
        failures.append("ADHERENCE_ORDER_INVALID:safe<balanced")
    if float(balanced.get("adherence_min", 0.0)) < float(stress.get("adherence_min", 0.0)):
        failures.append("ADHERENCE_ORDER_INVALID:balanced<stress")
    if float(safe.get("ttft_ceiling_ms", 0.0)) > float(balanced.get("ttft_ceiling_ms", 0.0)):
        failures.append("TTFT_ORDER_INVALID:safe>balanced")
    if float(balanced.get("ttft_ceiling_ms", 0.0)) > float(stress.get("ttft_ceiling_ms", 0.0)):
        failures.append("TTFT_ORDER_INVALID:balanced>stress")
    if float(safe.get("decode_floor_tps", 0.0)) < float(balanced.get("decode_floor_tps", 0.0)):
        failures.append("DECODE_FLOOR_ORDER_INVALID:safe<balanced")
    if float(balanced.get("decode_floor_tps", 0.0)) < float(stress.get("decode_floor_tps", 0.0)):
        failures.append("DECODE_FLOOR_ORDER_INVALID:balanced<stress")

    matrix_paths = [Path(token.strip()) for token in str(args.matrix_configs).split(",") if token.strip()]
    for matrix_path in matrix_paths:
        payload = _load(matrix_path)
        profile_name = str(payload.get("context_sweep_profile") or "").strip()
        contexts = payload.get("context_sweep_contexts")
        if profile_name not in profiles:
            failures.append(f"{matrix_path}:INVALID_CONTEXT_SWEEP_PROFILE")
        if not isinstance(contexts, list) or not contexts:
            failures.append(f"{matrix_path}:INVALID_CONTEXT_SWEEP_CONTEXTS")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "profiles": str(Path(args.profiles)).replace("\\", "/"),
        "matrix_configs": [str(path).replace("\\", "/") for path in matrix_paths],
        "failures": failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
