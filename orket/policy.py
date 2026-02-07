import json
from pathlib import Path
from orket.filesystem import FilesystemPolicy

def create_session_policy(workspace: str, references: list[str] = None) -> FilesystemPolicy:
    """
    Creates a fresh, isolated policy for a single orchestration session.
    """
    # Default base policy (could also be loaded from a global config)
    spaces = {
        "domain": str(Path.cwd()),
        "workspace": workspace,
        "references": references or []
    }
    
    # Standard security rules
    policy_rules = {
        "read_scope": ["workspace", "reference", "domain"],
        "write_scope": ["workspace"]
    }

    return FilesystemPolicy(spaces=spaces, policy=policy_rules)