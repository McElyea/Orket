import json
from pathlib import Path
from orket.filesystem import FilesystemPolicy

def load_policy(config_path: Path | str = "orket/permissions.json") -> FilesystemPolicy:
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    spaces = cfg.get("spaces", {})
    policy = cfg.get("policy", {})

    return FilesystemPolicy(spaces=spaces, policy=policy)
