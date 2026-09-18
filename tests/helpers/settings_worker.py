"""Independent process for actual settings restart and native admission proof."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from orket import settings
from orket.core.contracts.local_file_lock import LocalFileLockError


def main() -> int:
    operation, settings_path, preferences_path = sys.argv[1:]
    settings.set_settings_file(Path(settings_path))
    settings.set_preferences_file(Path(preferences_path))
    try:
        if operation == "preferences":
            print(json.dumps(settings.load_user_preferences()))
        elif operation == "save":
            settings.save_user_settings({"from_process": True})
            print(json.dumps({"saved": True}))
        else:
            raise ValueError("unknown settings worker operation")
    except (OSError, ValueError, LocalFileLockError) as exc:
        print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
