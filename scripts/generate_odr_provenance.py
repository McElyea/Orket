from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _run_text(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True)
        raw = proc.stdout or b""
        if not raw:
            return ""
        try:
            return raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="ignore").strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_ms(started_at: str | None, ended_at: str | None) -> int | None:
    start = _parse_iso(started_at)
    end = _parse_iso(ended_at)
    if start is None or end is None:
        return None
    delta = end - start
    return int(delta.total_seconds() * 1000)


def _parse_ollama_list() -> dict[str, dict[str, Any]]:
    raw = _run_text(["ollama", "list"])
    rows: dict[str, dict[str, Any]] = {}
    if not raw:
        return rows
    lines = [line for line in raw.splitlines() if line.strip()]
    for line in lines[1:]:
        parts = re.split(r"\s{2,}", line.strip())
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        rows[name] = {
            "name": name,
            "ollama_id": parts[1].strip() if len(parts) > 1 else None,
        }
    return rows


def _normalize_ollama_version(raw: str) -> str | None:
    text = str(raw or "").strip()
    if not text:
        return None
    match = re.search(r"(\d+\.\d+\.\d+(?:[-+._a-zA-Z0-9]*)?)", text)
    if match is not None:
        return match.group(1)
    return text


def _extract_quantization(show_output: str) -> str | None:
    if not show_output:
        return None
    for line in show_output.splitlines():
        lowered = line.strip().lower()
        if "quantization" in lowered:
            tokens = line.split(":", 1)
            if len(tokens) == 2 and tokens[1].strip():
                return tokens[1].strip()
            values = re.split(r"\s{2,}|\t+", line.strip())
            if values:
                return values[-1].strip()
    return None


def _resolve_model_metadata(model_name: str, ollama_list: dict[str, dict[str, Any]], enable_probes: bool) -> dict[str, Any]:
    base = {
        "name": model_name,
        "ollama_id": (ollama_list.get(model_name) or {}).get("ollama_id"),
        "quantization": None,
    }
    if not enable_probes:
        return base
    show_output = _run_text(["ollama", "show", model_name])
    base["quantization"] = _extract_quantization(show_output)
    return base


def _cpu_model(enable_probes: bool) -> str | None:
    name = platform.processor() or None
    if name:
        return name
    if not enable_probes:
        return None
    raw = _run_text(["wmic", "cpu", "get", "Name", "/value"])
    for line in raw.splitlines():
        if line.strip().lower().startswith("name="):
            value = line.split("=", 1)[1].strip()
            if value:
                return value
    return None


def _physical_cores(enable_probes: bool) -> int | None:
    if not enable_probes:
        return None
    raw = _run_text(["wmic", "cpu", "get", "NumberOfCores", "/value"])
    for line in raw.splitlines():
        if line.strip().lower().startswith("numberofcores="):
            value = line.split("=", 1)[1].strip()
            if value.isdigit():
                return int(value)
    return None


def _ram_total_gb(enable_probes: bool) -> float | None:
    if not enable_probes:
        return None
    if platform.system().lower() == "windows":
        raw = _run_text(["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"])
        for line in raw.splitlines():
            if line.strip().lower().startswith("totalphysicalmemory="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    return round(int(value) / (1024**3), 2)
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return round((page_size * pages) / (1024**3), 2)
    except (AttributeError, ValueError, OSError):
        return None


def _gpu_snapshot(enable_probes: bool) -> dict[str, Any]:
    payload = {
        "gpu_model": None,
        "vram_total_gb": None,
        "driver_version": None,
    }
    if not enable_probes:
        return payload
    raw = _run_text(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if not raw:
        return payload
    first = raw.splitlines()[0].strip()
    parts = [item.strip() for item in first.split(",")]
    if len(parts) >= 1:
        payload["gpu_model"] = parts[0] or None
    if len(parts) >= 2:
        try:
            payload["vram_total_gb"] = round(float(parts[1]) / 1024.0, 2)
        except ValueError:
            payload["vram_total_gb"] = None
    if len(parts) >= 3:
        payload["driver_version"] = parts[2] or None
    return payload


def _git_snapshot(enable_probes: bool) -> dict[str, Any]:
    payload = {
        "orket_git_commit": None,
        "git_dirty": None,
        "git_branch": None,
    }
    if not enable_probes:
        return payload
    payload["orket_git_commit"] = _run_text(["git", "rev-parse", "--short", "HEAD"]) or None
    payload["git_branch"] = _run_text(["git", "branch", "--show-current"]) or None
    status = _run_text(["git", "status", "--short"])
    payload["git_dirty"] = bool(status.strip()) if status is not None else None
    return payload


def _host_snapshot(enable_probes: bool) -> dict[str, Any]:
    host = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "cpu_model": _cpu_model(enable_probes=enable_probes),
        "cpu_logical_cores": os.cpu_count(),
        "cpu_physical_cores": _physical_cores(enable_probes=enable_probes),
        "ram_total_gb": _ram_total_gb(enable_probes=enable_probes),
    }
    host.update(_gpu_snapshot(enable_probes=enable_probes))
    return host


def _load_runs(input_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name in {"index.json", "provenance.json"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        results = payload.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            started = result.get("started_at")
            ended = result.get("ended_at")
            rows.append(
                {
                    "file": path.name,
                    "generated_at_utc": payload.get("generated_at"),
                    "started_at_utc": started,
                    "ended_at_utc": ended,
                    "duration_ms": _duration_ms(started, ended),
                    "architect_model": str(result.get("architect_model") or ""),
                    "auditor_model": str(result.get("auditor_model") or ""),
                    "runner_round_budget": (payload.get("config") or {}).get("rounds")
                    if isinstance(payload.get("config"), dict)
                    else None,
                    "gen_params": {
                        "temperature": (payload.get("config") or {}).get("temperature")
                        if isinstance(payload.get("config"), dict)
                        else None,
                        "timeout": (payload.get("config") or {}).get("timeout")
                        if isinstance(payload.get("config"), dict)
                        else None,
                    },
                }
            )
    return rows


def generate_provenance(input_dir: Path, output_path: Path, enable_probes: bool = True) -> dict[str, Any]:
    runs = _load_runs(input_dir)
    ollama_version_raw = _run_text(["ollama", "--version"]) if enable_probes else ""
    ollama_version = _normalize_ollama_version(ollama_version_raw)
    ollama_rows = _parse_ollama_list() if enable_probes else {}
    host = _host_snapshot(enable_probes=enable_probes)
    git = _git_snapshot(enable_probes=enable_probes)

    run_rows: list[dict[str, Any]] = []
    for row in runs:
        models = [
            _resolve_model_metadata(row["architect_model"], ollama_rows, enable_probes=enable_probes),
            _resolve_model_metadata(row["auditor_model"], ollama_rows, enable_probes=enable_probes),
        ]
        run_rows.append(
            {
                "file": row["file"],
                "generated_at_utc": row["generated_at_utc"],
                "started_at_utc": row["started_at_utc"],
                "ended_at_utc": row["ended_at_utc"],
                "duration_ms": row["duration_ms"],
                "runner_round_budget": row["runner_round_budget"],
                "host": host,
                "runtime": {
                    "ollama_version": ollama_version or None,
                    **git,
                },
                "models": models,
                "gen_params": row["gen_params"],
            }
        )

    payload = {
        "prov_v": "1.0.0",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "root": str(input_dir).replace("\\", "/"),
        "run_count": len(run_rows),
        "runs": run_rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ODR provenance sidecar for published ODR runs.")
    parser.add_argument("--input-dir", default="benchmarks/published/ODR")
    parser.add_argument("--out", default="benchmarks/published/ODR/provenance.json")
    parser.add_argument("--no-probes", action="store_true", help="Skip system/runtime probes for deterministic test mode.")
    args = parser.parse_args()
    payload = generate_provenance(
        input_dir=Path(args.input_dir),
        output_path=Path(args.out),
        enable_probes=not args.no_probes,
    )
    print(f"Wrote {args.out} (runs={payload['run_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
