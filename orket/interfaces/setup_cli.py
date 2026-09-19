"""Interactive project initialization: python -m orket.interfaces.setup_cli."""
import asyncio
import os
import sys
from pathlib import Path

from orket.application.services.setup_service import SetupService
from orket.application.services.user_settings_service import SettingsLocation


def main() -> int:
    try:
        root = Path.cwd()
        location = SettingsLocation(root, os.environ.get("ORKET_DURABLE_ROOT", ".orket/durable"))
        print("Orket EOS Initialization Wizard\n")
        choices = {
            "name": input("Organization Name [Vibe Rail]: ") or "Vibe Rail",
            "vision": input("Vision Statement: ") or "Autonomous engineering excellence.",
            "ethos": input("Core Ethos: ") or "Local-first sovereignty.",
            "workspace": input("Workspace Path [./workspace]: ") or "./workspace",
            "model": input("Model/Asset Path [./model]: ") or "./model",
            "module_profile": input("Module Profile [developer-local]: ") or "developer-local",
        }
        result = asyncio.run(SetupService(root, location).initialize(choices))
        print("\nInitialization complete!")
        print(f"Config saved to: {result['organization']}")
        print(f"Workspace ready at: {result['workspace']}")
        print("Next: Add your first Team and Epic to start the loop.")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except (OSError, ValueError, RuntimeError, EOFError) as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
