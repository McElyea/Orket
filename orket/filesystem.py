import os
from dataclasses import dataclass
from typing import List, Dict, Literal, Optional

Scope = Literal["workspace", "reference", "domain"]

@dataclass
class Spaces:
    work_domain: Optional[str]
    workspaces: List[str]
    reference_spaces: List[str]
    launch_dir: str  # always readable, non-recursive

@dataclass
class Policy:
    read_scope: List[Scope]
    write_scope: List[Scope]

class FilesystemPolicy:
    """
    Declarative filesystem policy over three spaces:

      - WorkDomain: broad working area
      - Workspaces: isolated task-specific directories
      - ReferenceSpaces: read-only inputs

    Additional rule:
      - The directory Orket is launched from is always readable (non-recursive).
    """

    def __init__(self, spaces: Dict, policy: Dict):
        launch_dir = os.path.abspath(os.getcwd())

        self.spaces = Spaces(
            work_domain=spaces.get("work_domain"),
            workspaces=spaces.get("workspaces", []),
            reference_spaces=spaces.get("reference_spaces", []),
            launch_dir=launch_dir,
        )

        self.policy = Policy(
            read_scope=policy.get("read_scope", ["workspace", "reference", "domain"]),
            write_scope=policy.get("write_scope", ["workspace"]),
        )

    def add_workspace(self, path: str):
        abs_path = os.path.abspath(path)
        if abs_path not in self.spaces.workspaces:
            self.spaces.workspaces.append(abs_path)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _in(self, path: str, roots: List[str]) -> bool:
        path = os.path.abspath(path)
        if os.name == 'nt':
            path = path.lower()
            
        for r in roots:
            root_abs = os.path.abspath(r)
            if os.name == 'nt':
                root_abs = root_abs.lower()
                
            if path.startswith(root_abs):
                return True
        return False

    def _in_workspace(self, path: str) -> bool:
        return self._in(path, self.spaces.workspaces)

    def _in_reference(self, path: str) -> bool:
        return self._in(path, self.spaces.reference_spaces)

    def _in_domain(self, path: str) -> bool:
        if not self.spaces.work_domain:
            return False
        
        path_abs = os.path.abspath(path)
        domain_abs = os.path.abspath(self.spaces.work_domain)
        
        if os.name == 'nt':
            path_abs = path_abs.lower()
            domain_abs = domain_abs.lower()
            
        return path_abs.startswith(domain_abs)

    def _in_launch_dir_exact(self, path: str) -> bool:
        # Only allow reading the exact launch directory, not subdirectories
        path_abs = os.path.abspath(path)
        launch_abs = self.spaces.launch_dir
        
        if os.name == 'nt':
            path_abs = path_abs.lower()
            launch_abs = launch_abs.lower()
            
        return path_abs == launch_abs

    # ---------------------------------------------------------
    # Scope resolution
    # ---------------------------------------------------------

    def _scopes_for_path(self, path: str) -> List[Scope]:
        scopes: List[Scope] = []
        if self._in_workspace(path):
            scopes.append("workspace")
        if self._in_reference(path):
            scopes.append("reference")
        if self._in_domain(path):
            scopes.append("domain")
        return scopes

    # ---------------------------------------------------------
    # Read permissions
    # ---------------------------------------------------------

    def can_read(self, path: str) -> bool:
        path = os.path.abspath(path)

        # Always allow reading the launch directory itself
        if self._in_launch_dir_exact(path):
            return True

        path_scopes = self._scopes_for_path(path)
        if not path_scopes:
            return False

        for scope in self.policy.read_scope:
            if scope in path_scopes:
                return True

        return False

    # ---------------------------------------------------------
    # Write permissions
    # ---------------------------------------------------------

    def can_write(self, path: str) -> bool:
        path = os.path.abspath(path)

        # Never write to launch directory
        if self._in_launch_dir_exact(path):
            return False

        path_scopes = self._scopes_for_path(path)

        # Reference spaces are always read-only
        if "reference" in path_scopes:
            return False

        if not path_scopes:
            return False

        for scope in self.policy.write_scope:
            if scope in path_scopes:
                return True

        return False
