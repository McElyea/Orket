import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any

def get_installed_models() -> List[str]:
    """Runs 'ollama list' and returns a list of model names."""
    try:
        result = subprocess.run(
            ["ollama", "list"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) <= 1:
            return []
        
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])
        return models
    except Exception:
        return []

def discover_project_assets(department: str = "core") -> Dict[str, List[str]]:
    """Scans the model/{department} directory for available configurations."""
    root = Path(__file__).parent.parent / "model" / department
    assets = {
        "projects": [],
        "teams": [],
        "sequences": [],
        "environments": []
    }
    
    if not root.exists():
        return assets

    mapping = {
        "projects": "projects",
        "teams": "teams",
        "sequences": "sequences",
        "environments": "environments"
    }

    for key, folder in mapping.items():
        dir_path = root / folder
        if dir_path.exists():
            found = [p.stem for p in dir_path.rglob("*.json") if "schema" not in p.name.lower()]
            assets[key] = found
            
    return assets

from orket.settings import load_user_settings, save_user_settings

def perform_first_run_setup():
    """Detects hardware/models and saves initial optimized settings."""
    settings = load_user_settings()
    if settings.get("setup_complete"):
        return

    print("\n[FIRST RUN] Optimizing Orket for your hardware...")
    models = get_installed_models()
    
    # Heuristic for hardware optimization
    optimization = {
        "setup_complete": True,
        "hardware_profile": "auto-detected",
        "preferred_coder": "qwen3-coder:latest",
        "preferred_architect": "llama3.1:8b",
    }

    if any("14b" in m for m in models):
        optimization["preferred_coder"] = next(m for m in models if "coder" in m and "14b" in m)
        optimization["hardware_profile"] = "mid-range (14B optimized)"
    
    if any("r1:32b" in m for m in models):
        optimization["preferred_architect"] = next(m for m in models if "r1:32b" in m)
    elif any("33b" in m for m in models):
         optimization["preferred_architect"] = next(m for m in models if "33b" in m)

    save_user_settings(optimization)
    print(f"  > Detected Profile: {optimization['hardware_profile']}")
    print(f"  > Default Coder:    {optimization['preferred_coder']}")
    print(f"  > Default Architect: {optimization['preferred_architect']}")
    print("  > Settings stored in 'user_settings.json'\n")

def print_orket_manifest(department: str = "core"):
    """Prints a suggested 'playlist' of what can be run right now."""
    models = get_installed_models()
    assets = discover_project_assets(department)
    
    print("\n" + "="*50)
    print(f" ORKET DISCOVERY (Dept: {department})")
    print("="*50)
    
    print(f"\n[LOCAL ENGINES] ({len(models)} found)")
    
    def find_best(keywords, fallback="None found"):
        for m in models:
            if any(k in m.lower() for k in keywords):
                return m
        return fallback

    best_coder = find_best(["coder-32b", "coder-33b", "coder:14b", "coder"])
    best_arch = find_best(["r1:32b", "70b", "72b", "33b"], fallback=find_best(["llama3.1:8b"]))
    best_ds = find_best(["v2.5", "math", "coder:14b"])
    best_legal = find_best(["gemma3", "gemma2", "70b"])
    best_ux = find_best(["gemma3", "gemma2", "27b", "20b"])
    best_pm = find_best(["llama3.1:8b", "command-r", "8b"])

    print(f"  > Senior Staff (Coding): {best_coder}")
    print(f"  > Solutions Architect:    {best_arch}")
    print(f"  > Data Scientist:         {best_ds}")
    print(f"  > UI/UX & Design:         {best_ux}")
    print(f"  > Lawyer & Compliance:    {best_legal}")
    print(f"  > PM & Business Analyst:  {best_pm}")

    print(f"\n[PROJECTS]")
    for p in assets["projects"]:
        print(f"  - {p}")

    print(f"\n[TEAMS]")
    for t in assets["teams"]:
        print(f"  - {t}")

    print(f"\n[COMMAND SUGGESTION]")
    if assets["projects"]:
        proj = "standard" if "standard" in assets["projects"] else assets["projects"][0]
        print(f"  python main.py --project {proj} --department {department}")
    
    print("="*50 + "\n")
