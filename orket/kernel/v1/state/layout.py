"""One local-state layout and deterministic event/publication encoding authority."""

import json
from pathlib import Path
from typing import Any

from orket.adapters.storage import kernel_state_store as store
from orket.kernel.v1.canonical import LSI_VERSION_V1, canonical_json_bytes, fs_token

LSI_VERSION = LSI_VERSION_V1
DIR_INDEX = "index"
DIR_COMMITTED = "committed"
DIR_STAGING = "staging"
DIR_OBJECTS = "objects"
DIR_TRIPLETS = "triplets"
DIR_REFS = "refs"
DIR_BY_ID = "by_id"
I_REF_MULTISOURCE = "I_REF_MULTISOURCE"


def path_token(value: str) -> str:
    if type(value) is not str or not value or value in {".", ".."}:
        raise ValueError("E_KERNEL_STATE_INVALID_PATH_SEGMENT")
    return fs_token(value)


def root_index(root: str) -> Path:
    return Path(root) / DIR_INDEX


def scope_root(root: str, scope: str, run_id: str | None = None, turn_id: str | None = None) -> Path:
    base = root_index(root)
    if scope == DIR_COMMITTED:
        return base / DIR_COMMITTED
    if scope == DIR_STAGING:
        if not run_id or not turn_id:
            raise ValueError("staging scope requires run_id and turn_id")
        return base / DIR_STAGING / path_token(run_id) / path_token(turn_id)
    raise ValueError(f"unknown scope: {scope}")


def objects_dir(scope: Path) -> Path:
    return scope / DIR_OBJECTS


def triplets_dir(scope: Path) -> Path:
    return scope / DIR_TRIPLETS


def objects_path(scope: Path, digest: str) -> Path:
    return objects_dir(scope) / path_token(digest[:2]) / path_token(digest)


def triplets_path(scope: Path, stem: str) -> Path:
    relative = Path(stem)
    if not stem or relative.drive or relative.is_absolute() or ".." in relative.parts or relative == Path():
        raise ValueError("E_KERNEL_STATE_INVALID_STEM")
    path = (triplets_dir(scope) / relative).with_suffix(".json")
    if not path.is_relative_to(triplets_dir(scope)):
        raise ValueError("E_KERNEL_STATE_INVALID_STEM")
    return path


def refs_by_id_dir(scope: Path) -> Path:
    return scope / DIR_REFS / DIR_BY_ID


def refs_by_id_path(scope: Path, ref_type: str, ref_id: str) -> Path:
    return refs_by_id_dir(scope) / path_token(ref_type) / f"{path_token(ref_id)}.json"


def write_json(path: Path, value: Any) -> None:
    store.write_bytes(path, canonical_json_bytes(value))


def event_line(level: str, stage: str, code: str, loc: str, message: str, **details: Any) -> str:
    escaped = str(message).replace("\r", r"\r").replace("\n", r"\n")

    def fmt(value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return str(value).replace("\r", r"\r").replace("\n", r"\n")

    detail_text = " ".join(f"{key}={fmt(details[key])}" for key in sorted(details))
    return f"[{level}] [STAGE:{stage}] [CODE:{code}] [LOC:{loc}] {escaped} | {detail_text}"
