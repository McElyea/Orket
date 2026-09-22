"""Worker-only initialization effects with native organization-file admission."""
from pathlib import Path

from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes

side_effecting = True


class SetupProjectStore:
    side_effecting = True

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.organization = self.root / "config/organization.json"

    def guard(self):
        return NativeFileLocks(self.organization, suffix=".setup-locks", error_prefix="E_SETUP",
                               empty_key_error="E_SETUP_LOCK_KEY").hold_sync("organization")

    def publish(self, organization: bytes, *, workspace: str, model: str) -> dict[str, str]:
        target = self.organization.resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("E_SETUP_ORGANIZATION_ESCAPE")
        require_regular_or_absent(self.organization, error_code="E_SETUP_ORGANIZATION_NOT_REGULAR")
        workspace_root = (self.root / workspace).resolve()
        model_root = (self.root / model).resolve()
        directories = [workspace_root, *(model_root / "core" / name for name in
                        ("epics", "roles", "teams", "dialects", "environments"))]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            if not directory.is_dir():
                raise OSError("E_SETUP_DIRECTORY_UNVERIFIED")
        write_verified_bytes(target, organization, error_code="E_SETUP_ORGANIZATION_UNVERIFIED")
        return {"organization": str(target), "workspace": str(workspace_root), "model": str(model_root)}
