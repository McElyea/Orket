from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


class BaseTools:
    def __init__(self, workspace_root: Path, references: List[Path]):
        self.workspace_root = workspace_root
        self.references = references

    def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
        """
        Resolve and validate a file path against security policy.
        """
        p = Path(path_str)
        if not p.is_absolute():
            p = self.workspace_root / p

        resolved = p.resolve()
        workspace_resolved = self.workspace_root.resolve()

        in_workspace = resolved.is_relative_to(workspace_resolved)
        in_references = any(resolved.is_relative_to(r.resolve()) for r in self.references)

        if not (in_workspace or in_references):
            raise PermissionError(f"Access to path '{path_str}' is denied by security policy.")

        if write and not in_workspace:
            raise PermissionError(f"Write access to path '{path_str}' is denied.")

        return resolved
