from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "vram_total_mb",
    "vram_used_mb",
    "ttft_ms",
    "prefill_tps",
    "decode_tps",
    "thermal_start_c",
    "thermal_end_c",
    "kernel_launch_ms",
    "model_load_ms",
]

OPTIONAL_FIELDS = [
    "pcie_throughput_gbps",
    "cuda_graph_warmup_ms",
    "gpu_clock_mhz",
    "power_draw_watts",
    "fan_speed_percent",
]

ALLOWED_STATUS = {
    "OK",
    "OPTIONAL_FIELD_MISSING",
    "NOT_APPLICABLE",
    "REQUIRED_FIELD_MISSING",
    "PARSE_ERROR",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate quant sidecar parse policy contract.")
    parser.add_argument("--summary", required=True, help="Path to quant sweep summary JSON.")
    parser.add_argument("--out", default="", help="Optional output path for report JSON.")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Summary must be a JSON object.")
    return payload


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    failures: list[str] = []
    checked_rows = 0

    sessions = summary.get("sessions") if isinstance(summary.get("sessions"), list) else []
    for s_idx, session in enumerate(sessions):
        rows = session.get("per_quant") if isinstance(session, dict) and isinstance(session.get("per_quant"), list) else []
        for r_idx, row in enumerate(rows):
            if not isinstance(row, dict):
                failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:invalid_type")
                continue
            sidecar = row.get("hardware_sidecar")
            if not isinstance(sidecar, dict):
                failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:missing:hardware_sidecar")
                continue
            checked_rows += 1
            for key in REQUIRED_FIELDS + OPTIONAL_FIELDS + ["sidecar_parse_status", "sidecar_parse_errors"]:
                if key not in sidecar:
                    failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:missing:{key}")

            status = str(sidecar.get("sidecar_parse_status") or "").strip().upper()
            if status not in ALLOWED_STATUS:
                failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:invalid:sidecar_parse_status:{status}")

            errors = sidecar.get("sidecar_parse_errors")
            if not isinstance(errors, list):
                failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:invalid:sidecar_parse_errors")
                errors = []

            if status == "OK":
                for key in REQUIRED_FIELDS:
                    if not isinstance(sidecar.get(key), (int, float)):
                        failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:ok_missing_numeric:{key}")

            if status == "OPTIONAL_FIELD_MISSING":
                invalid = [e for e in errors if not str(e).startswith("missing:")]
                if invalid:
                    failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:optional_invalid_errors")
            if status == "REQUIRED_FIELD_MISSING":
                if not errors:
                    failures.append(f"sessions:{s_idx}:per_quant:{r_idx}:required_missing_errors_empty")

    report = {
        "status": "PASS" if not failures else "FAIL",
        "summary": str(Path(args.summary)).replace("\\", "/"),
        "checked_rows": checked_rows,
        "failures": failures,
    }
    text = json.dumps(report, indent=2)
    print(text)
    out_text = str(args.out or "").strip()
    if out_text:
        out_path = Path(out_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())

