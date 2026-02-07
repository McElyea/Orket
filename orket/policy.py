import json
from pathlib import Path
from orket.filesystem import FilesystemPolicy

def create_session_policy(workspace: str, references: list[str] = None) -> FilesystemPolicy:

    """

    Creates a fresh, isolated policy for a single orchestration session.

    """

    # Align keys with Spaces dataclass in filesystem.py

    spaces = {

        "work_domain": str(Path.cwd()),

        "workspaces": [workspace],

        "reference_spaces": references or []

    }

    

    # Standard security rules

    policy_rules = {

        "read_scope": ["workspace", "reference", "domain"],

        "write_scope": ["workspace"]

    }



    return FilesystemPolicy(spaces=spaces, policy=policy_rules)
