import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from orket.orket import ConfigLoader

def get_installed_models() -> List[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        return [line.split()[0] for line in lines[1:] if line.split()]
    except: return []

def discover_project_assets(department: str = "core") -> Dict[str, List[str]]:
    loader = ConfigLoader(Path("model"), department)
    return {
        "rocks": loader.list_assets("rocks"),
        "epics": loader.list_assets("epics"),
        "teams": loader.list_assets("teams"),
    }

from orket.settings import load_user_settings, save_user_settings

def perform_first_run_setup():
    if load_user_settings().get("setup_complete"): return
    print("\n[FIRST RUN] Optimizing Orket...")
    save_user_settings({"setup_complete": True, "hardware_profile": "auto-detected"})

def print_orket_manifest(department: str = "core"):
    from orket.hardware import get_current_profile, can_handle_model_tier, ModelTier
    models, assets, hw = get_installed_models(), discover_project_assets(department), get_current_profile()
    
    print(f"\n{'='*50}\n ORKET EOS DISCOVERY (Dept: {department})\n Hardware: {hw.cpu_cores} Cores | {hw.ram_gb:.1f}GB | {hw.vram_gb:.1f}GB\n{'='*50}")
    
    def find_best(keywords, tier):
        if not can_handle_model_tier(tier, hw): return f"Skipped ({tier})"
        for m in models:
            if any(k in m.lower() for k in keywords): return m
        return "None found"

    print(f"\n[LOCAL ENGINES]\n  > Coder: {find_best(['coder'], ModelTier.T3_MID)}\n  > Arch:  {find_best(['llama', 'r1'], ModelTier.T2_BASE)}")
    print(f"\n[ROCKS]"); [print(f"  - {r}") for r in assets["rocks"]]
    print(f"\n[EPICS]"); [print(f"  - {e}") for e in assets["epics"]]
    print(f"\n[COMMAND SUGGESTION]\n  python main.py --epic standard\n{'='*50}\n")