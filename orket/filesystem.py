import os


class FilesystemPolicy:
    """
    Implements the DomainSpace / WorkSpace / ReferenceSpace model
    combined with a declarative write_policy.
    """

    def __init__(self, spaces: dict, policy: dict):
        # Spaces
        self.work_domain = spaces.get("work_domain")
        self.workspaces = spaces.get("workspaces", [])
        self.reference_spaces = spaces.get("reference_spaces", [])

        # Policy
        self.write_policy = policy.get("write_policy", "workspace-first")

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _in(self, path, roots):
        path = os.path.abspath(path)
        for r in roots:
            if path.startswith(os.path.abspath(r)):
                return True
        return False

    def in_workspace(self, path):
        return self._in(path, self.workspaces)

    def in_reference(self, path):
        return self._in(path, self.reference_spaces)

    def in_work_domain(self, path):
        if not self.work_domain:
            return False
        return os.path.abspath(path).startswith(os.path.abspath(self.work_domain))

    # ---------------------------------------------------------
    # Read permissions
    # ---------------------------------------------------------

    def can_read(self, path: str) -> bool:
        path = os.path.abspath(path)

        if self.in_workspace(path):
            return True

        if self.in_reference(path):
            return True

        if self.in_work_domain(path):
            return True

        return False

    # ---------------------------------------------------------
    # Write permissions (policy-driven)
    # ---------------------------------------------------------

    def can_write(self, path: str) -> bool:
        path = os.path.abspath(path)

        # ReferenceSpace is always read-only
        if self.in_reference(path):
            return False

        # Policy modes
        if self.write_policy == "workspace-only":
            return self.in_workspace(path)

        if self.write_policy == "workspace-first":
            if self.workspaces:
                return self.in_workspace(path)
            else:
                return self.in_work_domain(path)

        if self.write_policy == "domain-only":
            return self.in_work_domain(path)

        if self.write_policy == "disabled":
            return False

        # Unknown policy → safest default
        return False