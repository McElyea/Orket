# orket/hardware.py
import psutil
import subprocess
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class HardwareProfile:
    cpu_cores: int
    ram_gb: float
    vram_gb: float
    has_nvidia: bool

def get_vram_info() -> float:
    """Detects NVIDIA VRAM using nvidia-smi."""
    try:
        # Request vram in MB
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True
        )
        # May return multiple lines for multiple GPUs
        total_vram = 0
        for line in res.stdout.strip().splitlines():
            total_vram += int(line)
        return total_vram / 1024.0 # Convert to GB
    except Exception:
        return 0.0

def get_current_profile() -> HardwareProfile:
    ram = psutil.virtual_memory().total / (1024**3)
    cpu = psutil.cpu_count(logical=False) or 0
    vram = get_vram_info()
    return HardwareProfile(
        cpu_cores=cpu,
        ram_gb=ram,
        vram_gb=vram,
        has_nvidia=(vram > 0)
    )

class ToolTier:
    """Definitions for Hardware Requirements."""
    TIER_0_UTILITY = "utility"   # No reqs
    TIER_1_COMPUTE = "compute"   # 8GB RAM, 4 Cores (PDF/Docx)
    TIER_2_VISION  = "vision"    # 8GB VRAM (Local Vision Models)
    TIER_3_CREATOR = "creator"   # 12GB VRAM + 16GB RAM (Stable Diffusion)
    TIER_4_ULTRA   = "ultra"     # 16GB+ VRAM + 32GB RAM (High-res Flux/SDXL)

class ModelTier:
    """Estimates for 4-bit quantized local models."""
    T1_MINI  = "mini"   # < 4B models (3GB VRAM)
    T2_BASE  = "base"   # 7B-9B models (8GB VRAM)
    T3_MID   = "mid"    # 12B-14B models (12GB VRAM)
    T4_HIGH  = "high"   # 30B-35B models (24GB VRAM)
    T5_ULTRA = "ultra"  # 70B+ models (48GB+ VRAM)

def can_handle_model_tier(tier: str, profile: HardwareProfile) -> bool:
    vram = profile.vram_gb
    if tier == ModelTier.T1_MINI: return True # Everyone can run 1B
    if tier == ModelTier.T2_BASE: return vram >= 6 or profile.ram_gb >= 16
    if tier == ModelTier.T3_MID:  return vram >= 10
    if tier == ModelTier.T4_HIGH: return vram >= 20
    if tier == ModelTier.T5_ULTRA: return vram >= 40
    return False

def can_handle_tier(tier: str, profile: HardwareProfile) -> bool:
    if tier == ToolTier.TIER_0_UTILITY:
        return True
    
    if tier == ToolTier.TIER_1_COMPUTE:
        return profile.ram_gb >= 8 and profile.cpu_cores >= 4
    
    if tier == ToolTier.TIER_2_VISION:
        return profile.has_nvidia and profile.vram_gb >= 6
    
    if tier == ToolTier.TIER_3_CREATOR:
        return profile.has_nvidia and profile.vram_gb >= 10 and profile.ram_gb >= 16
        
    if tier == ToolTier.TIER_4_ULTRA:
        return profile.has_nvidia and profile.vram_gb >= 16 and profile.ram_gb >= 32
        
    return False
