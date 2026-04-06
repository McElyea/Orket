from pathlib import Path
from typing import Any, Literal

Scope = Literal["workspace", "reference", "domain"]


class FilesystemPolicy:
    """
    Declarative filesystem policy using secure Path.is_relative_to() checks.

    Three scopes govern access: `workspace` for task-local writable roots, `reference`
    for explicit read-only inputs, and `domain` for the broader launch/work domain.
    `launch_dir` is tracked only so the session can anchor its default domain; it does
    not bypass scope checks.
    """

    def __init__(self, spaces: dict[str, Any], policy: dict[str, Any]) -> None:
        self.work_domain: Path | None = Path(spaces["work_domain"]).resolve() if spaces.get("work_domain") else None
        self.workspaces: list[Path] = [Path(w).resolve() for w in spaces.get("workspaces", [])]
        self.reference_spaces: list[Path] = [Path(r).resolve() for r in spaces.get("reference_spaces", [])]
        self.launch_dir: Path = Path.cwd().resolve()

        self.read_scope: list[Scope] = policy.get("read_scope", ["workspace", "reference", "domain"])
        self.write_scope: list[Scope] = policy.get("write_scope", ["workspace"])

    def add_workspace(self, path: str) -> None:
        resolved = Path(path).resolve()
        if resolved not in self.workspaces:
            self.workspaces.append(resolved)

    def _scopes_for_path(self, path: Path) -> list[Scope]:
        scopes: list[Scope] = []
        if any(path.is_relative_to(w) for w in self.workspaces):
            scopes.append("workspace")
        if any(path.is_relative_to(r) for r in self.reference_spaces):
            scopes.append("reference")
        if self.work_domain and path.is_relative_to(self.work_domain):
            scopes.append("domain")
        return scopes

    def can_read(self, path: str) -> bool:
        resolved = Path(path).resolve()
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


def create_session_policy(workspace: str, references: list[str] | None = None) -> FilesystemPolicy:
    """Creates a fresh, isolated policy for a single orchestration session."""
    spaces = {"work_domain": str(Path.cwd()), "workspaces": [workspace], "reference_spaces": references or []}
    policy_rules = {"read_scope": ["workspace", "reference", "domain"], "write_scope": ["workspace"]}
    return FilesystemPolicy(spaces=spaces, policy=policy_rules)
