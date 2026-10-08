# orket/hardware.py
import os
import platform
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psutil

from orket.adapters.execution.owned_io import require_sync_context

_VRAM_CACHE = {
    "ts": 0.0,
    "total": 0.0,
    "used": 0.0,
}
_VRAM_CACHE_LOCK = threading.Lock()


side_effecting = True


@dataclass
class HardwareProfile:
    cpu_cores: int
    ram_gb: float
    vram_gb: float | None
    has_nvidia: bool
    memory_model: str = "unknown"
    architecture: str = "unknown"
    gpu_observation: str = "unobserved"


def get_vram_info() -> float:
    """Detects NVIDIA VRAM using nvidia-smi."""
    require_sync_context(code="E_HARDWARE_REQUIRES_NATIVE_OWNER")
    try:
        # Request vram in MB
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
        # May return multiple lines for multiple GPUs
        total_vram = 0
        for line in res.stdout.strip().splitlines():
            total_vram += int(line)
        return total_vram / 1024.0  # Convert to GB
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
        return 0.0


def get_current_profile() -> HardwareProfile:
    require_sync_context(code="E_HARDWARE_REQUIRES_NATIVE_OWNER")
    host = platform.uname()
    ram = psutil.virtual_memory().total / (1024**3)
    cpu = psutil.cpu_count(logical=False) or 0
    if _apple_silicon(host.system, host.machine):
        return HardwareProfile(cpu, ram, None, False, "unified", host.machine, "metal_unverified")
    vram = get_vram_info()
    return HardwareProfile(cpu, ram, vram, vram > 0, "dedicated" if vram > 0 else "unknown",
                           host.machine, "nvidia_observed" if vram > 0 else "unobserved")


def _apple_silicon(system: str, machine: str) -> bool:
    return system == "Darwin" and machine.lower() in {"arm64", "aarch64"}


def get_metrics_snapshot() -> dict[str, Any]:
    """Returns real-time usage stats for graphs."""
    require_sync_context(code="E_HARDWARE_REQUIRES_NATIVE_OWNER")
    host = platform.uname()
    vm = psutil.virtual_memory()
    if _apple_silicon(host.system, host.machine):
        return {
            "cpu_percent": psutil.cpu_percent(interval=None), "ram_percent": vm.percent,
            "vram_gb_used": None, "vram_total_gb": None, "memory_model": "unified",
            "unified_memory_gb": vm.total / (1024**3), "gpu_observation": "metal_unverified",
            "architecture": host.machine, "timestamp": datetime.now(UTC).isoformat(),
        }
    cache_ttl_sec = 5.0
    try:
        cache_ttl_sec = max(0.0, float(os.getenv("ORKET_METRICS_VRAM_CACHE_SEC", "5")))
    except (TypeError, ValueError):
        cache_ttl_sec = 5.0

    vram = _cached_vram_metrics(cache_ttl_sec)
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": vm.percent,
        "vram_gb_used": vram["used"],
        "vram_total_gb": vram["total"],
        "memory_model": "dedicated" if vram["total"] > 0 else "unknown",
        "gpu_observation": "nvidia_observed" if vram["total"] > 0 else "unobserved",
        "architecture": host.machine,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _cached_vram_metrics(cache_ttl_sec: float) -> dict[str, float]:
    with _VRAM_CACHE_LOCK:
        now = time.monotonic()
        age = now - _VRAM_CACHE["ts"]
        if age <= cache_ttl_sec:
            return {"total": _VRAM_CACHE["total"], "used": _VRAM_CACHE["used"]}

        total = get_vram_info()
        used = get_vram_usage()
        _VRAM_CACHE["ts"] = now
        _VRAM_CACHE["total"] = total
        _VRAM_CACHE["used"] = used
        return {"total": total, "used": used}


def get_vram_usage() -> float:
    require_sync_context(code="E_HARDWARE_REQUIRES_NATIVE_OWNER")
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        )
        total_used = 0
        for line in res.stdout.strip().splitlines():
            total_used += int(line)
        return total_used / 1024.0
    except (subprocess.CalledProcessError, OSError, ValueError):
        return 0.0


class ToolTier:
    """Definitions for Hardware Requirements."""

    TIER_0_UTILITY = "utility"  # No reqs
    TIER_1_COMPUTE = "compute"  # 8GB RAM, 4 Cores (PDF/Docx)
    TIER_2_VISION = "vision"  # 8GB VRAM (Local Vision Models)
    TIER_3_CREATOR = "creator"  # 12GB VRAM + 16GB RAM (Stable Diffusion)
    TIER_4_ULTRA = "ultra"  # 16GB+ VRAM + 32GB RAM (High-res Flux/SDXL)


class ModelTier:
    """Estimates for 4-bit quantized local models."""

    T1_MINI = "mini"  # < 4B models (3GB VRAM)
    T2_BASE = "base"  # 7B-9B models (8GB VRAM)
    T3_MID = "mid"  # 12B-14B models (12GB VRAM)
    T4_HIGH = "high"  # 30B-35B models (24GB VRAM)
    T5_ULTRA = "ultra"  # 70B+ models (48GB+ VRAM)


def can_handle_model_tier(tier: str, profile: HardwareProfile) -> bool | None:
    """Legacy advisory heuristic; None means memory fit has not been established."""
    vram = profile.vram_gb
    if vram is None:
        return None
    if tier == ModelTier.T1_MINI:
        return True  # Everyone can run 1B
    if tier == ModelTier.T2_BASE:
        return vram >= 6 or profile.ram_gb >= 16
    if tier == ModelTier.T3_MID:
        return vram >= 10
    if tier == ModelTier.T4_HIGH:
        return vram >= 20
    if tier == ModelTier.T5_ULTRA:
        return vram >= 40
    return False


def can_handle_tier(tier: str, profile: HardwareProfile) -> bool:
    if tier == ToolTier.TIER_0_UTILITY:
        return True

    if tier == ToolTier.TIER_1_COMPUTE:
        return profile.ram_gb >= 8 and profile.cpu_cores >= 4

    if profile.vram_gb is None:
        return False  # These optional tool tiers require the existing NVIDIA path.

    if tier == ToolTier.TIER_2_VISION:
        return profile.has_nvidia and profile.vram_gb >= 6

    if tier == ToolTier.TIER_3_CREATOR:
        return profile.has_nvidia and profile.vram_gb >= 10 and profile.ram_gb >= 16

    if tier == ToolTier.TIER_4_ULTRA:
        return profile.has_nvidia and profile.vram_gb >= 16 and profile.ram_gb >= 32

    return False
