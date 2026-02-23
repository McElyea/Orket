from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, TypeVar


LSI_VERSION_V1 = "lsi/v1"


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Canonical JSON bytes (Spec-002):
    - UTF-8
    - sort_keys=True
    - separators=(",", ":")
    - ensure_ascii=False
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def structural_digest(canonical_bytes: bytes) -> str:
    return hashlib.sha256(canonical_bytes).hexdigest()


def digest_of(obj: Any) -> str:
    return structural_digest(canonical_json_bytes(obj))


def fs_token(value: str) -> str:
    """
    Filesystem-safe token for IDs and stems used in path segments.
    """
    return (
        value.replace("%", "%25")
        .replace("/", "%2F")
        .replace("\\", "%5C")
        .replace(":", "%3A")
    )


T = TypeVar("T")


def sorted_deterministically(values: Iterable[T]) -> list[T]:
    """
    Minimal deterministic helper used by state modules.
    """
    return sorted(values)  # type: ignore[arg-type]
