from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_sweep.constants import OPTIONAL_SIDECAR_FIELDS, REQUIRED_SIDECAR_FIELDS


def quant_report_out(base_dir: Path, model_id: str, quant_tag: str) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())
    safe_quant = re.sub(r"[^a-zA-Z0-9_.-]+", "_", quant_tag.strip())
    return base_dir / safe_model / f"{safe_quant}_determinism_report.json"


def sidecar_out(base_dir: Path, model_id: str, quant_tag: str) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())
    safe_quant = re.sub(r"[^a-zA-Z0-9_.-]+", "_", quant_tag.strip())
    return base_dir / "sidecar" / safe_model / f"{safe_quant}_hardware_sidecar.json"


def default_sidecar_result() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enabled": False,
        "return_code": None,
        "out_file": "",
        "sidecar_parse_status": "NOT_APPLICABLE",
        "sidecar_parse_errors": [],
    }
    for key in REQUIRED_SIDECAR_FIELDS + OPTIONAL_SIDECAR_FIELDS:
        payload[key] = None
    return payload


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_sidecar_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "vram_total_mb": ["vram_total_mb", "vram_total", "memory_total_mb"],
        "vram_used_mb": ["vram_used_mb", "vram_used", "memory_used_mb"],
        "ttft_ms": ["ttft_ms", "ttft"],
        "prefill_tps": ["prefill_tps", "prompt_tps", "prefill_tokens_per_second"],
        "decode_tps": ["decode_tps", "generation_tps", "decode_tokens_per_second"],
        "thermal_start_c": ["thermal_start_c", "temp_start_c", "temperature_start_c"],
        "thermal_end_c": ["thermal_end_c", "temp_end_c", "temperature_end_c"],
        "kernel_launch_ms": ["kernel_launch_ms", "kernel_ms"],
        "model_load_ms": ["model_load_ms", "load_ms"],
        "pcie_throughput_gbps": ["pcie_throughput_gbps", "pcie_gbps"],
        "cuda_graph_warmup_ms": ["cuda_graph_warmup_ms", "graph_warmup_ms"],
        "gpu_clock_mhz": ["gpu_clock_mhz", "clock_mhz"],
        "power_draw_watts": ["power_draw_watts", "power_watts"],
        "fan_speed_percent": ["fan_speed_percent", "fan_percent"],
    }
    normalized = default_sidecar_result()
    for canonical, keys in aliases.items():
        value = None
        for key in keys:
            if key in payload:
                value = _coerce_number(payload.get(key))
                break
        normalized[canonical] = value
    return normalized


def run_sidecar(
    *,
    template: str,
    timeout_sec: int,
    model_id: str,
    quant_tag: str,
    runtime_target: str,
    execution_mode: str,
    out_file: Path,
) -> dict[str, Any]:
    result_payload = default_sidecar_result()
    if not str(template or "").strip():
        return result_payload

    out_file.parent.mkdir(parents=True, exist_ok=True)
    command = str(template).format(
        model_id=model_id,
        quant_tag=quant_tag,
        runtime_target=runtime_target,
        execution_mode=execution_mode,
        out_file=str(out_file).replace("\\", "/"),
    )
    argv = shlex.split(command, posix=os.name != "nt")
    if not argv:
        raise SystemExit("hardware sidecar template resolved to an empty command")
    result = subprocess.run(
        argv,
        shell=False,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(1, int(timeout_sec)),
    )
    stdout = str(result.stdout or "")
    stderr = str(result.stderr or "")
    parsed: dict[str, Any] | None = None
    try:
        payload = json.loads(stdout) if stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        parsed = payload

    normalized = default_sidecar_result()
    parse_errors: list[str] = []
    parse_status = "OK"
    if int(result.returncode) != 0 and ("nvidia-smi" in stderr.lower() or "nvidia-smi" in stdout.lower()):
        parse_status = "NOT_APPLICABLE"
        parse_errors = ["nvidia_smi_unavailable"]
    elif parsed is None:
        parse_status = "PARSE_ERROR"
        parse_errors = ["invalid_format:sidecar_payload"]
    else:
        normalized = _normalize_sidecar_payload(parsed)
        missing_required = [key for key in REQUIRED_SIDECAR_FIELDS if normalized.get(key) is None]
        missing_optional = [key for key in OPTIONAL_SIDECAR_FIELDS if normalized.get(key) is None]
        if missing_required:
            parse_status = "REQUIRED_FIELD_MISSING"
            parse_errors = [f"missing:{key}" for key in missing_required]
        elif missing_optional:
            parse_status = "OPTIONAL_FIELD_MISSING"
            parse_errors = [f"missing:{key}" for key in missing_optional]
    parse_errors = sorted(parse_errors)

    sidecar_payload = {
        **normalized,
        "enabled": True,
        "command": command,
        "return_code": int(result.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed,
        "sidecar_parse_status": parse_status,
        "sidecar_parse_errors": parse_errors,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    out_file.write_text(json.dumps(sidecar_payload, indent=2) + "\n", encoding="utf-8")
    return {
        **normalized,
        "enabled": True,
        "return_code": int(result.returncode),
        "out_file": str(out_file).replace("\\", "/"),
        "parsed": parsed if isinstance(parsed, dict) else {},
        "sidecar_parse_status": parse_status,
        "sidecar_parse_errors": parse_errors,
    }
