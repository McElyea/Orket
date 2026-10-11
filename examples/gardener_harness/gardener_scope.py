"""Explicit snapshot selection; unselected contents never become audit evidence."""
import json
import os
import re
from pathlib import PurePosixPath

from orket_extension_sdk import canonical_digest_sha256

DEFAULT_FILES = frozenset({"README.md", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md",
    "LICENSE", "LICENSE.md", "LICENSE.txt", "CODEOWNERS", "pyproject.toml", "package.json", "Cargo.toml",
    "go.mod", "requirements.txt", "setup.cfg", "setup.py", "Makefile", "Dockerfile"})
DEFAULT_DIRECTORIES = (PurePosixPath("docs"), PurePosixPath(".github"), PurePosixPath(".gitea"))
TEXT_SUFFIXES = frozenset({".md", ".rst", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg"})


def relative_scope(value: str) -> PurePosixPath:
    path = PurePosixPath(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or ":" in value:
        raise ValueError("snapshot scope must be a relative file or directory within its source root")
    return path


def target_scopes(environment: dict[str, str]) -> tuple[PurePosixPath, ...]:
    if "ORKET_GARDENER_TARGET_PATHS" not in environment:
        return ()
    values = json.loads(environment["ORKET_GARDENER_TARGET_PATHS"])
    if (not isinstance(values, list) or not 1 <= len(values) <= 64
            or any(not isinstance(value, str) for value in values)):
        raise ValueError("ORKET_GARDENER_TARGET_PATHS must be a JSON list of 1..64 relative files/directories")
    return tuple(relative_scope(value) for value in values)


def wanted_entry(entry: dict, tree: dict, index: int, prompt: str, scopes) -> bool:
    prefix = PurePosixPath(tree["selected"].relative_to(tree["root"]).as_posix())
    relative = PurePosixPath(entry["path"]).relative_to(prefix)
    if index > 0:
        return True
    if scopes:
        return any(relative.is_relative_to(scope) for scope in scopes)
    if str(relative) in DEFAULT_FILES or (relative.suffix.lower() in TEXT_SUFFIXES
            and any(relative.is_relative_to(path) for path in DEFAULT_DIRECTORIES)):
        return True
    names = [str(relative), (tree["root"] / entry["path"]).as_posix()]
    if os.name == "nt":
        prompt, names = prompt.casefold(), [name.casefold() for name in names]
    return any(re.search(r"(?<![\w./])" + re.escape(name) + r"(?![\w./])", prompt) for name in names)


def inventory_payload(trees: list[dict]) -> list[dict]:
    return [{**tree, "root": str(tree["root"]), "selected": str(tree["selected"])} for tree in trees]


def coverage_listing(trees: list[dict], sources: dict) -> dict:
    repositories = []
    for index, tree in enumerate(trees):
        included = {item["path"] for item in sources.values() if item.get("repository") == index}
        complete = len(tree["entries"]) <= 128
        root_names = {entry["path"] for entry in tree["entries"]
                      if len(PurePosixPath(entry["path"]).parts) == 1}
        root_names = set(sorted(root_names)[:128])
        visible = [entry for entry in tree["entries"] if complete or entry["path"] in included
                   or entry["path"] in root_names]
        repositories.append({"repository": index, "commit": tree["commit"],
            "files": [{"path": entry["path"], "mode": entry["mode"]} for entry in visible],
            "inventory_complete_in_prompt": complete, "tracked_file_count": len(tree["entries"]),
            "omitted_inventory_entries": len(tree["entries"]) - len(visible),
            "included_contents": sorted(included), "unread_file_count": len(tree["entries"]) - len(included),
            "inventory_digest": "sha256:" + canonical_digest_sha256(tree["entries"])})
    return {"repositories": repositories, "content_coverage": "selected_files_only",
            "full_inventory_artifact": "snapshot-inventory.json",
            "instruction": "Names prove presence only. Unread contents and omitted inventory entries are unknown."}


def byte_limits(environment: dict[str, str]) -> tuple[int, int]:
    limits = tuple(int(environment.get(key, default)) for key, default in (
        ("ORKET_GARDENER_MAX_FILE_BYTES", "16384"), ("ORKET_GARDENER_MAX_SNAPSHOT_BYTES", "65536")))
    if not 1 <= limits[0] <= limits[1] <= 524288:
        raise ValueError("snapshot byte limits require 1 <= file <= total <= 524288; token limits also apply")
    return limits
