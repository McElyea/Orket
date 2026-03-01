from __future__ import annotations

import json
import hashlib
from typing import Any, Dict


NON_SEMANTIC_KEYS = {
    "timestamp",
    "timestamps",
    "created_at",
    "updated_at",
    "recorded_at",
    "run_id",
    "run_ids",
    "run_path",
    "path",
    "paths",
    "temp_path",
    "elapsed_ms",
    "duration_ms",
    "latency_ms",
    "perf",
    "metrics_runtime",
}

UNORDERED_LIST_KEYS = {
    "nodes",
    "edges",
    "relationships",
    "links",
    "refs",
}


def _normalize_string(value: str) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def canonicalize(obj: Any, *, _parent_key: str = "") -> Any:
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for key in sorted(obj.keys()):
            if key in NON_SEMANTIC_KEYS:
                continue
            cleaned[str(key)] = canonicalize(obj[key], _parent_key=str(key))
        return cleaned

    if isinstance(obj, list):
        canonical_items = [canonicalize(item, _parent_key=_parent_key) for item in obj]
        if _parent_key in UNORDERED_LIST_KEYS:
            canonical_items.sort(key=lambda item: canonical_bytes(item))
        return canonical_items

    if isinstance(obj, str):
        return _normalize_string(obj)

    return obj


def canonical_bytes(obj: Any) -> bytes:
    canonical_obj = canonicalize(obj)
    text = json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def raw_signature(obj: Any) -> str:
    stream: list[str] = []
    _walk_raw(obj, stream)
    digest = hashlib.sha256("\n".join(stream).encode("utf-8")).hexdigest()
    return digest


def first_diff_path(a: bytes, b: bytes) -> str:
    try:
        left = json.loads(a.decode("utf-8"))
        right = json.loads(b.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return "$"

    if left == right:
        return "$"

    return _first_diff_path_obj(left, right, "$")


def _first_diff_path_obj(left: Any, right: Any, path: str) -> str:
    if type(left) is not type(right):
        return path

    if isinstance(left, dict):
        left_keys = sorted(left.keys())
        right_keys = sorted(right.keys())
        if left_keys != right_keys:
            for key in sorted(set(left_keys) | set(right_keys)):
                if key not in left or key not in right:
                    return f"{path}/{_escape_key(key)}"
        for key in left_keys:
            if left[key] != right[key]:
                return _first_diff_path_obj(left[key], right[key], f"{path}/{_escape_key(key)}")
        return path

    if isinstance(left, list):
        if len(left) != len(right):
            return path
        for idx, (li, ri) in enumerate(zip(left, right)):
            if li != ri:
                return _first_diff_path_obj(li, ri, f"{path}/{idx}")
        return path

    return path


def _escape_key(key: str) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def _walk_raw(value: Any, stream: list[str], path: str = "$") -> None:
    if isinstance(value, dict):
        stream.append(f"{path}|dict|{len(value)}")
        for key, item in value.items():
            key_text = str(key)
            stream.append(f"{path}|key|{key_text}")
            _walk_raw(item, stream, f"{path}/{_escape_key(key_text)}")
        return

    if isinstance(value, list):
        stream.append(f"{path}|list|{len(value)}")
        for index, item in enumerate(value):
            _walk_raw(item, stream, f"{path}/{index}")
        return

    if isinstance(value, str):
        stream.append(f"{path}|str|{_normalize_string(value)}")
        return

    stream.append(f"{path}|{type(value).__name__}|{value!r}")
