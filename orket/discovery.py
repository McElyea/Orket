import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from orket.infrastructure.async_file_tools import AsyncFileTools
from orket.orket import ConfigLoader
from orket.schema import RockConfig, EpicConfig, TeamConfig, EngineRegistry

def get_installed_models() -> List[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        # Filter out 'NAME' header and empty lines
        return [line.split()[0] for line in lines if line and not line.startswith("NAME")]
    except (subprocess.SubprocessError, FileNotFoundError, OSError): return []

def refresh_engine_mappings():
    """
    Scans installed models and hardware to find the best match for each category.
    Returns a dictionary of recommended overrides.
    """
    from orket.hardware import get_current_profile, can_handle_model_tier
    hw = get_current_profile()
    models = get_installed_models()
    
    registry_path = Path("model/core/engines.json")
    if not registry_path.exists(): return {}
    
    fs = AsyncFileTools(Path("."))
    registry = EngineRegistry.model_validate_json(fs.read_file_sync(str(registry_path)))
    recommendations = {}

    for cat, mapping in registry.mappings.items():
        if not can_handle_model_tier(mapping.tier, hw):
            continue
            
        best_match = None
        for m in models:
            if any(k in m.lower() for k in mapping.keywords):
                # Simple heuristic: pick the one with 'latest' or the first one found
                if not best_match or "latest" in m:
                    best_match = m
        
        recommendations[cat] = best_match or mapping.fallback
        
    return recommendations

def get_engine_recommendations():
    """
    Cross-references hardware profile + installed models against the Catalog
    to suggest what the user is missing for a 'Best-in-Class' setup.
    """
    from orket.hardware import get_current_profile, can_handle_model_tier
    hw = get_current_profile()
    installed = get_installed_models()
    
    registry_path = Path("model/core/engines.json")
    if not registry_path.exists(): return []
    
    fs = AsyncFileTools(Path("."))
    registry = EngineRegistry.model_validate_json(fs.read_file_sync(str(registry_path)))
    suggestions = []

    for category, mapping in registry.mappings.items():
        # Check if we already have a 'High Tier' model for this category
        has_high_tier = False
        for m in installed:
            if any(k in m.lower() for k in mapping.keywords):
                # If the installed model is in our catalog and is high tier, we're good
                # (This is a simplification, but works for local discovery)
                pass

        # Find the best model in the catalog that the hardware CAN handle
        best_in_catalog = None
        for item in mapping.catalog:
            if can_handle_model_tier(item.tier, hw):
                # If it's not installed, it's a candidate
                if item.model not in installed:
                    # Prefer higher tiers
                    if not best_in_catalog or item.tier > best_in_catalog.tier:
                        best_in_catalog = item

        if best_in_catalog:
            suggestions.append({
                "category": category,
                "suggestion": best_in_catalog.model,
                "tier": best_in_catalog.tier,
                "reason": best_in_catalog.description,
                "command": f"ollama run {best_in_catalog.model}"
            })
            
    return suggestions

def discover_project_assets(department: str = "core") -> Dict[str, List[str]]:
    loader = ConfigLoader(Path("model"), department)
    return {
        "rocks": loader.list_assets("rocks"),
        "epics": loader.list_assets("epics"),
        "teams": loader.list_assets("teams"),
    }

from orket.settings import load_user_settings, save_user_settings

def perform_first_run_setup():
    # Run Structural Reconciliation on every startup to clean up orphans
    try:
        from orket.domain.reconciler import StructuralReconciler
        reconciler = StructuralReconciler()
        reconciler.reconcile_all()
    except (RuntimeError, ValueError, OSError, ImportError) as e:
        print(f"  [WARN] Structural Reconciliation failed: {e}")

    if load_user_settings().get("setup_complete"): return
    print("\n[FIRST RUN] Orket EOS Orkestrated.")
    print("  Recommendation: Orkestrate the initialization rock to optimize your models.")
    print("  Command: python main.py --rock initialize_orket")
    save_user_settings({"setup_complete": True, "hardware_profile": "auto-detected"})

def print_orket_manifest(department: str = "core"):
    from orket.hardware import get_current_profile, can_handle_model_tier, ModelTier
    models, assets, hw = get_installed_models(), discover_project_assets(department), get_current_profile()
    loader = ConfigLoader(Path("model"), department)
    
    print(f"\n{'='*60}\n ORKET EOS MANIFEST (Dept: {department})\n Hardware: {hw.cpu_cores} Cores | {hw.ram_gb:.1f}GB RAM | {hw.vram_gb:.1f}GB VRAM\n{'='*60}")
    
    def find_best(keywords, tier):
        if not can_handle_model_tier(tier, hw): return f"Skipped ({tier})"
        for m in models:
            if any(k in m.lower() for k in keywords): return m
        return "None found"

    print(f"\n[LOCAL ENGINES]\n  > Coder: {find_best(['coder'], ModelTier.T3_MID)}\n  > Arch:  {find_best(['llama', 'r1'], ModelTier.T2_BASE)}")

    # --- UPGRADE SUGGESTIONS ---
    recs = get_engine_recommendations()
    if recs:
        print(f"\n[MEMBER UPGRADES AVAILABLE]")
        for r in recs:
            print(f"  ! {r['category'].upper():<10} | Suggestion: {r['suggestion']:<20} | {r['reason']}")
            print(f"    Command: {r['command']}")

    if assets["rocks"]:
        print(f"\n[ROCKS & ACCOUNTABILITY]")
        for rock_name in assets["rocks"]:
            try:
                rock = loader.load_asset("rocks", rock_name, RockConfig)
                print(f"  - ROCK: {rock.name}")
                for entry in rock.epics:
                    dept = entry["department"]
                    epic_name = entry["epic"]
                    
                    # Load the Epic to see the Seats
                    try:
                        dept_loader = ConfigLoader(Path("model"), dept)
                        epic = dept_loader.load_asset("epics", epic_name, EpicConfig)
                        team = dept_loader.load_asset("teams", epic.team, TeamConfig)
                        
                        seats = [i.seat for i in epic.issues]
                        unique_seats = list(dict.fromkeys(seats)) # Preserve order
                        
                        print(f"    * {dept.upper():<12} | Epic: {epic_name:<20} | Members: {', '.join(unique_seats)}")
                    except (FileNotFoundError, ValueError, KeyError) as e:
                        print(f"    * {dept.upper():<12} | Epic: {epic_name:<20} | [Error: {e}]")
            except (FileNotFoundError, ValueError) as e:
                print(f"  - ROCK: {rock_name} [Metadata load failed: {e}]")

    else:
        print(f"\n[EPICS (Standalone)]")
        for e in assets["epics"]:
            print(f"  - {e}")

    print(f"\n[COMMAND SUGGESTION]\n  python main.py --rock {assets['rocks'][0] if assets['rocks'] else '...'} --department {department}\n{'='*60}\n")
