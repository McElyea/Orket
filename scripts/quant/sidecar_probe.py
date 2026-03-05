from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Emit normalized sidecar probe payload.")
    parser.add_argument("--backend", required=True, choices=["nvidia", "amd", "cpu"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--quant", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args()


def _probe_nvidia() -> dict[str, Any]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=memory.total,memory.used,temperature.gpu,clocks.sm,power.draw,fan.speed",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    line = str(result.stdout or "").strip().splitlines()[0] if str(result.stdout or "").strip() else ""
    if not line:
        return {}
    parts = [chunk.strip() for chunk in line.split(",")]
    if len(parts) < 6:
        return {}
    try:
        return {
            "vram_total_mb": float(parts[0]),
            "vram_used_mb": float(parts[1]),
            "thermal_end_c": float(parts[2]),
            "gpu_clock_mhz": float(parts[3]),
            "power_draw_watts": float(parts[4]),
            "fan_speed_percent": float(parts[5]),
        }
    except ValueError:
        return {}


def main() -> int:
    args = _parse_args()
    payload: dict[str, Any] = {
        "probe_generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "backend": str(args.backend),
        "model": str(args.model),
        "quant": str(args.quant),
        # Required fields with safe numeric defaults.
        "vram_total_mb": 0.0,
        "vram_used_mb": 0.0,
        "ttft_ms": 0.0,
        "prefill_tps": 0.0,
        "decode_tps": 0.0,
        "thermal_start_c": 0.0,
        "thermal_end_c": 0.0,
        "kernel_launch_ms": 0.0,
        "model_load_ms": 0.0,
    }
    if str(args.backend) == "nvidia":
        payload.update(_probe_nvidia())
        if payload.get("thermal_end_c") is not None:
            payload["thermal_start_c"] = payload["thermal_end_c"]
    if str(args.backend) == "amd":
        payload["probe_note"] = "AMD probe fallback emitted default numeric fields."
    if str(args.backend) == "cpu":
        payload["probe_note"] = "CPU-only sidecar emitted default numeric fields."

    text = json.dumps(payload, indent=2)
    print(text)
    out_path = Path(str(args.out).strip())
    if str(out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
