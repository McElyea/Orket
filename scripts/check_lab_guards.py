from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROFILE_TO_RATIO = {
    "safe": 0.50,
    "balanced": 0.80,
    "stress": 0.95,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check cooldown and VRAM preflight guard diagnostics from sweep summary.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--cooldown-target-c", type=float, default=50.0)
    parser.add_argument("--vram-profile", default="safe", choices=["safe", "balanced", "stress"])
    parser.add_argument("--allow-skip", action="store_true", help="Treat SKIP status as success.")
    return parser.parse_args()


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    summary = _load_summary(Path(args.summary))
    vram_ratio_limit = float(PROFILE_TO_RATIO[str(args.vram_profile)])
    failures: list[str] = []
    skips: list[str] = []
    checks = 0

    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        model_id = str(session.get("model_id") or "unknown")
        rows = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            quant_tag = str(row.get("quant_tag") or "unknown")
            sidecar = row.get("hardware_sidecar") if isinstance(row.get("hardware_sidecar"), dict) else {}
            thermal_start = sidecar.get("thermal_start_c")
            vram_total = sidecar.get("vram_total_mb")
            vram_used = sidecar.get("vram_used_mb")
            parse_status = str(sidecar.get("sidecar_parse_status") or "NOT_APPLICABLE").strip().upper()
            prefix = f"{model_id}:{quant_tag}"

            if not isinstance(thermal_start, (int, float)):
                skips.append(f"{prefix}:COOLDOWN_SKIPPED_MISSING_THERMAL_START")
            else:
                checks += 1
                if float(thermal_start) > float(args.cooldown_target_c):
                    failures.append(f"{prefix}:COOLDOWN_TARGET_NOT_MET:{thermal_start}>{args.cooldown_target_c}")

            if not isinstance(vram_total, (int, float)) or float(vram_total) <= 0 or not isinstance(vram_used, (int, float)):
                if parse_status in {"NOT_APPLICABLE", "OPTIONAL_FIELD_MISSING"}:
                    skips.append(f"{prefix}:VRAM_GUARD_SKIPPED_{parse_status}")
                else:
                    skips.append(f"{prefix}:VRAM_GUARD_SKIPPED_MISSING_METRICS")
            else:
                checks += 1
                ratio = float(vram_used) / float(vram_total)
                if ratio > vram_ratio_limit:
                    failures.append(
                        f"{prefix}:VRAM_RATIO_EXCEEDED:{ratio:.6f}>{vram_ratio_limit:.6f}"
                    )

    status = "PASS"
    if failures:
        status = "FAIL"
    elif checks == 0:
        status = "SKIP"
    report = {
        "status": status,
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "profile": str(args.vram_profile),
        "thresholds": {
            "cooldown_target_c": float(args.cooldown_target_c),
            "vram_ratio_limit": vram_ratio_limit,
        },
        "checks": checks,
        "failures": failures,
        "skip_reasons": skips,
    }
    print(json.dumps(report, indent=2))
    if status == "FAIL":
        return 2
    if status == "SKIP" and not bool(args.allow_skip):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
