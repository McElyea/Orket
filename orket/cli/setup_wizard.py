"""
Orket Setup Wizard - Phase 5: Production Readiness

Interactive CLI tool to initialize an Orket workspace.
Created during the v1.0 maturation phase.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any

from orket.schema import OrganizationConfig, BrandingConfig, ArchitecturePrescription


def run_wizard():
    """Starts the interactive initialization process."""
    print("==========================================")
    print("   Orket EOS Initialization Wizard        ")
    print("==========================================")
    print("\nThis wizard will set up your local Orket environment.\n")

    # 1. Organization Setup
    org_name = input("Organization Name [Vibe Rail]: ") or "Vibe Rail"
    org_vision = input("Vision Statement: ") or "Autonomous engineering excellence."
    org_ethos = input("Core Ethos: ") or "Local-first sovereignty."

    # 2. Path Setup
    workspace_path = input("Workspace Path [./workspace]: ") or "./workspace"
    model_path = input("Model/Asset Path [./model]: ") or "./model"

    config = OrganizationConfig(
        name=org_name,
        vision=org_vision,
        ethos=org_ethos,
        branding=BrandingConfig(),
        architecture=ArchitecturePrescription(idesign_threshold=7),
        departments=["core"]
    )

    # 3. Create Directories
    base = Path.cwd()
    (base / workspace_path).mkdir(parents=True, exist_ok=True)
    (base / model_path / "core" / "epics").mkdir(parents=True, exist_ok=True)
    (base / model_path / "core" / "roles").mkdir(parents=True, exist_ok=True)
    (base / model_path / "core" / "teams").mkdir(parents=True, exist_ok=True)
    (base / model_path / "core" / "dialects").mkdir(parents=True, exist_ok=True)
    (base / model_path / "core" / "environments").mkdir(parents=True, exist_ok=True)

    # 4. Save Config
    config_dir = base / "config"
    config_dir.mkdir(exist_ok=True)
    
    org_file = config_dir / "organization.json"
    with org_file.open("w", encoding="utf-8") as f:
        f.write(config.model_dump_json(indent=4))

    print("\n✅ Initialization complete!")
    print(f"   Config saved to: {org_file}")
    print(f"   Workspace ready at: {workspace_path}")
    print("\nNext: Add your first Team and Epic to start the loop.")


if __name__ == "__main__":
    run_wizard()
