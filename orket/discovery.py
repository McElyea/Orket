import subprocess
from pathlib import Path
from typing import Dict, List

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.logging import log_event
from orket.orket import ConfigLoader
from orket.project_paths import default_model_root, default_project_root, default_workspace_root
from orket.settings import load_user_settings, save_user_settings
from orket.schema import RockConfig, EpicConfig, TeamConfig, EngineRegistry


def _default_project_root() -> Path:
    return default_project_root()


def _default_model_root() -> Path:
    return default_model_root()


def _default_workspace_root() -> Path:
    return default_workspace_root()


def _model_tier_rank(tier: str) -> int:
    normalized = str(tier or "").strip().lower()
    return {
        "mini": 1,
        "base": 2,
        "mid": 3,
        "high": 4,
        "ultra": 5,
    }.get(normalized, 0)


def get_installed_models() -> List[str]:
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        # Filter out 'NAME' header and empty lines
        return [line.split()[0] for line in lines if line and not line.startswith("NAME")]
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []


def refresh_engine_mappings():
    """
    Scans installed models and hardware to find the best match for each category.
    Returns a dictionary of recommended overrides.
    """
    from orket.hardware import get_current_profile, can_handle_model_tier

    hw = get_current_profile()
    models = get_installed_models()

    registry_path = _default_model_root() / "core" / "engines.json"
    if not registry_path.exists():
        return {}

    fs = AsyncFileTools(_default_project_root())
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

    registry_path = _default_model_root() / "core" / "engines.json"
    if not registry_path.exists():
        return []

    fs = AsyncFileTools(_default_project_root())
    registry = EngineRegistry.model_validate_json(fs.read_file_sync(str(registry_path)))
    suggestions = []
    installed_lower = [str(item).strip().lower() for item in installed]

    for category, mapping in registry.mappings.items():
        best_installed_rank = 0
        for installed_model in installed_lower:
            # Prefer known catalog tier when the installed model is recognized.
            for item in mapping.catalog:
                model_name = str(item.model).strip().lower()
                if model_name == installed_model or model_name in installed_model:
                    best_installed_rank = max(best_installed_rank, _model_tier_rank(item.tier))
            # Keyword-only match is treated as minimal baseline confidence, not catalog-tier equivalence.
            if any(keyword in installed_model for keyword in mapping.keywords):
                best_installed_rank = max(best_installed_rank, 1)

        # Find the best model in the catalog that the hardware CAN handle
        best_in_catalog = None
        for item in mapping.catalog:
            if can_handle_model_tier(item.tier, hw):
                # If it's not installed, it's a candidate
                if str(item.model).strip().lower() not in installed_lower:
                    # Prefer higher tiers
                    if not best_in_catalog or _model_tier_rank(item.tier) > _model_tier_rank(best_in_catalog.tier):
                        best_in_catalog = item

        if best_in_catalog and _model_tier_rank(best_in_catalog.tier) > best_installed_rank:
            suggestions.append(
                {
                    "category": category,
                    "suggestion": best_in_catalog.model,
                    "tier": best_in_catalog.tier,
                    "reason": best_in_catalog.description,
                    "command": f"ollama run {best_in_catalog.model}",
                }
            )

    return suggestions


def discover_project_assets(department: str = "core") -> Dict[str, List[str]]:
    loader = ConfigLoader(_default_model_root(), department)
    return {
        "rocks": loader.list_assets("rocks"),
        "epics": loader.list_assets("epics"),
        "teams": loader.list_assets("teams"),
    }


def run_startup_reconciliation() -> str:
    """Run every-startup structural reconciliation and emit explicit path telemetry."""
    try:
        from orket.domain.reconciler import StructuralReconciler

        reconciler = StructuralReconciler(
            root_path=_default_model_root(),
            workspace=_default_workspace_root(),
        )
        reconciler.reconcile_all()
        log_event("discovery_startup_path", {"path": "reconciliation", "result": "success"})
        return "success"
    except (RuntimeError, ValueError, OSError, ImportError) as e:
        log_event("discovery_startup_path", {"path": "reconciliation", "result": "failed", "error": str(e)})
        log_event("discovery_reconcile_failed", {"error": str(e)})
        return "failed"


def perform_first_run_onboarding() -> str:
    """Run first-run-only onboarding and emit explicit path telemetry."""
    if load_user_settings().get("setup_complete"):
        log_event("discovery_startup_path", {"path": "no_op", "reason": "setup_complete"})
        return "no_op"
    print("\n[FIRST RUN] Orket EOS Orkestrated.")
    print("  Recommendation: Use the canonical card entrypoint for initialization to optimize your models.")
    print("  Command: python main.py --card initialize_orket")
    save_user_settings({"setup_complete": True, "hardware_profile": "auto-detected"})
    log_event("discovery_startup_path", {"path": "first_run_setup", "result": "completed"})
    return "first_run_setup"


def perform_startup_checks() -> Dict[str, str]:
    """Execute startup reconciliation plus first-run onboarding with explicit semantics."""
    reconciliation_result = run_startup_reconciliation()
    onboarding_result = perform_first_run_onboarding()
    return {"reconciliation": reconciliation_result, "onboarding": onboarding_result}


def perform_first_run_setup() -> Dict[str, str]:
    """Backward-compatible wrapper around explicit startup checks."""
    return perform_startup_checks()


def print_orket_manifest(department: str = "core"):
    from orket.hardware import get_current_profile, can_handle_model_tier, ModelTier

    models, assets, hw = get_installed_models(), discover_project_assets(department), get_current_profile()
    loader = ConfigLoader(_default_model_root(), department)

    manifest_header = (
        f"\n{'=' * 60}\n"
        f" ORKET EOS MANIFEST (Dept: {department})\n"
        f" Hardware: {hw.cpu_cores} Cores | {hw.ram_gb:.1f}GB RAM | {hw.vram_gb:.1f}GB VRAM\n"
        f"{'=' * 60}"
    )
    print(manifest_header)

    def find_best(keywords, tier):
        if not can_handle_model_tier(tier, hw):
            return f"Skipped ({tier})"
        for m in models:
            if any(k in m.lower() for k in keywords):
                return m
        return "None found"

    local_engines = (
        "\n[LOCAL ENGINES]\n"
        f"  > Coder: {find_best(['coder'], ModelTier.T3_MID)}\n"
        f"  > Arch:  {find_best(['llama', 'r1'], ModelTier.T2_BASE)}"
    )
    print(local_engines)

    # --- UPGRADE SUGGESTIONS ---
    recs = get_engine_recommendations()
    if recs:
        print("\n[MEMBER UPGRADES AVAILABLE]")
        for r in recs:
            print(f"  ! {r['category'].upper():<10} | Suggestion: {r['suggestion']:<20} | {r['reason']}")
            print(f"    Command: {r['command']}")

    if assets["rocks"]:
        print("\n[ROCKS & ACCOUNTABILITY]")
        for rock_name in assets["rocks"]:
            try:
                rock = loader.load_asset("rocks", rock_name, RockConfig)
                print(f"  - ROCK: {rock.name}")
                for entry in rock.epics:
                    dept = entry["department"]
                    epic_name = entry["epic"]

                    # Load the Epic to see the Seats
                    try:
                        dept_loader = ConfigLoader(_default_model_root(), dept)
                        epic = dept_loader.load_asset("epics", epic_name, EpicConfig)
                        dept_loader.load_asset("teams", epic.team, TeamConfig)

                        seats = [i.seat for i in epic.issues]
                        unique_seats = list(dict.fromkeys(seats))  # Preserve order

                        print(f"    * {dept.upper():<12} | Epic: {epic_name:<20} | Members: {', '.join(unique_seats)}")
                    except (FileNotFoundError, ValueError, KeyError) as e:
                        print(f"    * {dept.upper():<12} | Epic: {epic_name:<20} | [Error: {e}]")
            except (FileNotFoundError, ValueError) as e:
                print(f"  - ROCK: {rock_name} [Metadata load failed: {e}]")

    else:
        print("\n[EPICS (Standalone)]")
        for e in assets["epics"]:
            print(f"  - {e}")

    suggestion_rock = assets["rocks"][0] if assets["rocks"] else "..."
    print(f"\n[COMMAND SUGGESTION]\n  python main.py --card {suggestion_rock} --department {department}\n{'=' * 60}\n")
