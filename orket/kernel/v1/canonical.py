"""RFC 8785/JCS canonicalizer for object storage and turn-result digests.

This module is the cross-language digest authority. Domain-specific policies,
such as the ODR determinism surface, preprocess their data here before handing
it to the same RFC 8785 backend.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, TypeVar

LSI_VERSION_V1 = "lsi/v1"

# Orket default profile constraint for digested structures:
# integers only, within JS safe integer range (prevents cross-language drift).
JS_SAFE_INT_MAX = (2**53) - 1
JS_SAFE_INT_MIN = -JS_SAFE_INT_MAX


class CanonicalizationError(ValueError):
    """Raised when an object cannot be canonicalized under the Orket RFC-8785 profile."""


def _iter_json_values(obj: Any) -> Iterable[Any]:
    """
    Depth-first walk of a JSON-like structure.
    We treat only: dict, list/tuple, str, int, bool, None as valid.
    """
    if obj is None:
        return
    if isinstance(obj, (str, bool, int, float)):
        yield obj
        return
    if isinstance(obj, dict):
        # keys must be strings in JSON
        for k, v in obj.items():
            yield k
            yield from _iter_json_values(v)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_json_values(v)
        return

    # Anything else is not JSON
    yield obj


def _validate_orket_number_domain(obj: Any, *, allow_float: bool = False) -> None:
    """
    Orket constraint: no floats, no NaN/Infinity, and ints must be within JS safe integer range.
    (This is stricter than RFC 8785, by design.)
    """
    for v in _iter_json_values(obj):
        # dict keys yielded as strings, ok.
        # bool is a subclass of int in Python. Catch it here alongside str/None
        # before the int path so True/False are never validated as integers.
        if v is None or isinstance(v, (str, bool)):
            continue

        if isinstance(v, float):
            if allow_float:
                if not math.isfinite(v):
                    raise CanonicalizationError("Non-finite number encountered. RFC 8785 forbids NaN/Infinity.")
                continue
            raise CanonicalizationError("Non-integer number encountered (float). Orket digest profile forbids floats.")

        if isinstance(v, int):
            if v < JS_SAFE_INT_MIN or v > JS_SAFE_INT_MAX:
                raise CanonicalizationError(
                    f"Integer out of range for Orket digest profile: {v} "
                    f"(allowed [{JS_SAFE_INT_MIN}, {JS_SAFE_INT_MAX}])."
                )
            continue

        # If we got here, it’s a non-JSON type
        if not isinstance(v, (dict, list, tuple)):
            raise CanonicalizationError(f"Non-JSON value encountered during canonicalization: {type(v).__name__}")


def _jcs_canonicalize_to_str(obj: Any) -> str:
    """
    Canonicalize using an RFC 8785 implementation.

    Preference order:
      1) rfc8785 (Trail of Bits)
      2) jcs (Anders Rundgren's implementation packaged on PyPI)

    Returns canonical JSON text (no trailing newline).
    """
    # 1) Trail of Bits: rfc8785.py
    try:
        import rfc8785

        out = rfc8785.dumps(obj)
        if isinstance(out, (bytes, bytearray)):
            return bytes(out).decode("utf-8")
        if isinstance(out, str):
            return out
        raise CanonicalizationError(f"Unexpected rfc8785.dumps() return type: {type(out).__name__}")
    except ModuleNotFoundError:
        pass

    # 2) Anders Rundgren JCS package: jcs
    try:
        import jcs  # type: ignore[import-untyped]

        # PyPI "jcs" exposes canonicalize() and returns bytes.
        out = jcs.canonicalize(obj)
        if isinstance(out, (bytes, bytearray)):
            return bytes(out).decode("utf-8")
        if isinstance(out, str):
            return out
        raise CanonicalizationError(f"Unexpected jcs.canonicalize() return type: {type(out).__name__}")
    except ModuleNotFoundError:
        pass

    raise CanonicalizationError(
        "No RFC 8785 canonicalizer installed. Install one of:\n"
        "  pip install rfc8785   (recommended)\n"
        "  pip install jcs\n"
        "Refusing to fall back to non-RFC8785 canonicalization."
    )


def canonical_json_bytes(
    obj: Any, *, allow_non_rfc8785_fallback: bool = False, allow_float: bool = False
) -> bytes:
    """
    Canonical JSON bytes (Orket RFC-8785 profile):
      - Validate Orket number domain (integer-only, 53-bit safe)
      - Canonicalize using RFC 8785 (JCS)
      - Return UTF-8 bytes of the canonical JSON text
      - No BOM, no trailing newline (canonicalizers should already comply)

    If allow_non_rfc8785_fallback=True, will fall back to legacy Python json.dumps() behavior.
    (Not recommended; use only as a temporary bridge while wiring deps/tests.)

    If allow_float=True, finite floats are admitted for domain surfaces that
    already contain metric ratios. The default remains integer-only for durable
    object-storage digests.
    """
    _validate_orket_number_domain(obj, allow_float=allow_float)

    try:
        canonical = _jcs_canonicalize_to_str(obj)
        return canonical.encode("utf-8")
    except CanonicalizationError:
        if not allow_non_rfc8785_fallback:
            raise

    # Temporary fallback (NOT RFC 8785)
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


def normalized_turn_result_surface(turn_result: dict[str, Any]) -> dict[str, Any]:
    """
    Build the contract-only digest surface for TurnResult.
    Diagnostic-only fields are excluded or nullified:
      - events are excluded
      - issues[*].message is nullified
      - turn_result_digest is excluded from digest input
    """
    surface = copy.deepcopy(turn_result)
    surface.pop("events", None)
    surface.pop("turn_result_digest", None)
    issues = surface.get("issues")
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                issue["message"] = None
    return surface


def compute_turn_result_digest(turn_result: dict[str, Any]) -> str:
    return digest_of(normalized_turn_result_surface(turn_result))


def fs_token(value: str) -> str:
    """
    Filesystem-safe token for IDs and stems used in path segments.
    """
    return value.replace("%", "%25").replace("/", "%2F").replace("\\", "%5C").replace(":", "%3A")


T = TypeVar("T")


def sorted_deterministically(values: Iterable[T]) -> list[T]:
    """
    Minimal deterministic helper used by state modules.
    """
    return sorted(values, key=repr)


ODR_NON_SEMANTIC_KEYS = frozenset(
    {
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
)

ODR_UNORDERED_LIST_KEYS = frozenset(
    {
        "nodes",
        "edges",
        "relationships",
        "links",
        "refs",
    }
)


@dataclass(frozen=True)
class CanonicalPolicy:
    """Domain-specific preprocessing before canonical RFC 8785 serialization."""

    non_semantic_keys: frozenset[str] = field(default_factory=frozenset)
    unordered_list_keys: frozenset[str] = field(default_factory=frozenset)
    normalize_strings: bool = True
    allow_float: bool = False

    def normalize(self, obj: Any, *, _parent_key: str = "") -> Any:
        if isinstance(obj, dict):
            cleaned: dict[str, Any] = {}
            for key in sorted(obj.keys(), key=str):
                key_text = str(key)
                if key_text in self.non_semantic_keys:
                    continue
                cleaned[key_text] = self.normalize(obj[key], _parent_key=key_text)
            return cleaned

        if isinstance(obj, list):
            canonical_items = [self.normalize(item, _parent_key=_parent_key) for item in obj]
            if _parent_key in self.unordered_list_keys:
                keyed_items = [(self.canonical_bytes(item), item) for item in canonical_items]
                keyed_items.sort(key=lambda pair: pair[0])
                return [item for _, item in keyed_items]
            return canonical_items

        if isinstance(obj, str) and self.normalize_strings:
            return _normalize_string(obj)

        return obj

    def canonical_bytes(self, obj: Any) -> bytes:
        return canonical_json_bytes(self.normalize(obj), allow_float=self.allow_float)

    def digest(self, obj: Any) -> str:
        return structural_digest(self.canonical_bytes(obj))


ODR_CANONICAL_POLICY = CanonicalPolicy(
    non_semantic_keys=ODR_NON_SEMANTIC_KEYS,
    unordered_list_keys=ODR_UNORDERED_LIST_KEYS,
    allow_float=True,
)


def _normalize_string(value: str) -> str:
    return str(value).replace("\r\n", "\n").replace("\r", "\n")


def odr_canonicalize(obj: Any) -> Any:
    return ODR_CANONICAL_POLICY.normalize(obj)


def odr_canonical_json_bytes(obj: Any) -> bytes:
    return ODR_CANONICAL_POLICY.canonical_bytes(obj)


def odr_raw_signature(obj: Any) -> str:
    stream: list[str] = []
    _walk_raw(obj, stream)
    return hashlib.sha256("\n".join(stream).encode("utf-8")).hexdigest()


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
        for idx, (li, ri) in enumerate(zip(left, right, strict=False)):
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
