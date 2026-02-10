from pathlib import Path
from typing import List, Literal, Optional

Scope = Literal["workspace", "reference", "domain"]


class FilesystemPolicy:
    """
    Declarative filesystem policy using secure Path.is_relative_to() checks.

    Three spaces:
      - WorkDomain: broad working area
      - Workspaces: isolated task-specific directories
      - ReferenceSpaces: read-only inputs
    """

    def __init__(self, spaces: dict, policy: dict):
        self.work_domain: Optional[Path] = Path(spaces["work_domain"]).resolve() if spaces.get("work_domain") else None
        self.workspaces: List[Path] = [Path(w).resolve() for w in spaces.get("workspaces", [])]
        self.reference_spaces: List[Path] = [Path(r).resolve() for r in spaces.get("reference_spaces", [])]
        self.launch_dir: Path = Path.cwd().resolve()

        self.read_scope: List[Scope] = policy.get("read_scope", ["workspace", "reference", "domain"])
        self.write_scope: List[Scope] = policy.get("write_scope", ["workspace"])

    def add_workspace(self, path: str):
        resolved = Path(path).resolve()
        if resolved not in self.workspaces:
            self.workspaces.append(resolved)

    def _scopes_for_path(self, path: Path) -> List[Scope]:
        scopes: List[Scope] = []
        if any(path.is_relative_to(w) for w in self.workspaces):
            scopes.append("workspace")
        if any(path.is_relative_to(r) for r in self.reference_spaces):
            scopes.append("reference")
        if self.work_domain and path.is_relative_to(self.work_domain):
            scopes.append("domain")
        return scopes

    def can_read(self, path: str) -> bool:
        resolved = Path(path).resolve()
        if resolved == self.launch_dir:
            return True
        path_scopes = self._scopes_for_path(resolved)
        return any(scope in path_scopes for scope in self.read_scope)

    def can_write(self, path: str) -> bool:
        resolved = Path(path).resolve()
        if resolved == self.launch_dir:
            return False
        path_scopes = self._scopes_for_path(resolved)
        if "reference" in path_scopes:
            return False
        return any(scope in path_scopes for scope in self.write_scope)


def create_session_policy(workspace: str, references: list[str] = None) -> FilesystemPolicy:
    """Creates a fresh, isolated policy for a single orchestration session."""
    spaces = {
        "work_domain": str(Path.cwd()),
        "workspaces": [workspace],
        "reference_spaces": references or []
    }
    policy_rules = {
        "read_scope": ["workspace", "reference", "domain"],
        "write_scope": ["workspace"]
    }
    return FilesystemPolicy(spaces=spaces, policy=policy_rules)
