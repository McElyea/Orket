"""Model-root file operations; callers retain one owned worker and mutation guard."""
import json
from pathlib import Path

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes


class DriverResourceStore:
    side_effecting = True

    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, *parts: str) -> Path:
        candidate = self.root.joinpath(*parts).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("DRIVER_RESOURCE_OUT_OF_SURFACE")
        return candidate

    def departments(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and p.resolve().is_relative_to(self.root))

    def read(self, path: Path) -> dict:
        checked = self.path(str(path))
        payload = json.loads(checked.read_bytes())
        if not isinstance(payload, dict):
            raise ValueError("DRIVER_RESOURCE_EXPECTED_OBJECT")
        return payload

    def write(self, path: Path, payload: dict) -> None:
        checked = self.path(str(path))
        write_verified_bytes(checked, (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode())

    def guard(self):
        return NativeFileLocks(self.root, suffix=".driver-locks", error_prefix="DRIVER_RESOURCE",
                               empty_key_error="DRIVER_RESOURCE_LOCK_KEY").hold_sync("model")
