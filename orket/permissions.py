import os
import json


class FilesystemPolicy:
    """
    Implements the DomainSpace / WorkSpace / ReferenceSpace model.
    """

    def __init__(self, config: dict):
        self.work_domain = config.get("work_domain")              # string or None
        self.workspaces = config.get("workspaces", [])            # list
        self.reference_spaces = config.get("reference_spaces", [])# list

        # Progressive trust flags
        self.workspace_required_for_writes = config.get(
            "workspace_required_for_writes", True
        )
        self.reference_space_read_only = config.get(
            "reference_space_read_only", True
        )
        self.allow_writes_in_work_domain_if_no_workspace = config.get(
            "allow_writes_in_work_domain_if_no_workspace", True
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _in(self, path, roots):
        path = os.path.abspath(path)
        for r in roots:
            if path.startswith(os.path.abspath(r)):
                return True
        return False

    # ---------------------------------------------------------
    # Read permissions
    # ---------------------------------------------------------

    def can_read(self, path: str) -> bool:
        path = os.path.abspath(path)

        # Workspaces: always readable
        if self._in(path, self.workspaces):
            return True

        # Reference spaces: always readable
        if self._in(path, self.reference_spaces):
            return True

        # Work domain: readable if defined
        if self.work_domain and path.startswith(os.path.abspath(self.work_domain)):
            return True

        return False

    # ---------------------------------------------------------
    # Write permissions
    # ---------------------------------------------------------

    def can_write(self, path: str) -> bool:
        path = os.path.abspath(path)

        # If workspace is required for writes and we have one
        if self.workspace_required_for_writes and self.workspaces:
            return self._in(path, self.workspaces)

        # If no workspace is set, fallback to work domain
        if not self.workspaces and self.allow_writes_in_work_domain_if_no_workspace:
            if self.work_domain and path.startswith(os.path.abspath(self.work_domain)):
                return True

        # Reference spaces are always read-only
        if self.reference_space_read_only and self._in(path, self.reference_spaces):
            return False

        return False


# -------------------------------------------------------------
# Loader
# -------------------------------------------------------------

def load_permissions():
    path = os.path.join(os.getcwd(), "permissions.json")
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return FilesystemPolicy(config)