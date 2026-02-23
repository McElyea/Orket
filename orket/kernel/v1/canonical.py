from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, TypeVar

LSI_VERSION_V1 = "lsi/v1"

# Orket profile constraint for digested structures:
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


def _validate_orket_number_domain(obj: Any) -> None:
    """
    Orket constraint: no floats, no NaN/Infinity, and ints must be within JS safe integer range.
    (This is stricter than RFC 8785, by design.)
    """
    for v in _iter_json_values(obj):
        # dict keys yielded as strings, ok.
        if v is None or isinstance(v, (str, bool)):
            continue

        # bool is subclass of int in Python; ensure we don't treat True/False as numbers.
        if isinstance(v, bool):
            continue

        if isinstance(v, float):
            raise CanonicalizationError(
                "Non-integer number encountered (float). Orket digest profile forbids floats."
            )

        if isinstance(v, int):
            if v < JS_SAFE_INT_MIN or v > JS_SAFE_INT_MAX:
                raise CanonicalizationError(
                    f"Integer out of range for Orket digest profile: {v} "
                    f"(allowed [{JS_SAFE_INT_MIN}, {JS_SAFE_INT_MAX}])."
                )
            continue

        # If we got here, it’s a non-JSON type
        if not isinstance(v, (dict, list, tuple)):
            raise CanonicalizationError(
                f"Non-JSON value encountered during canonicalization: {type(v).__name__}"
            )


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
        import rfc8785  # type: ignore

        # The Trail of Bits docs expose a "dumps" style API.
        # If your installed version differs, you'll get a clear attribute error.
        return rfc8785.dumps(obj)  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        pass

    # 2) Anders Rundgren JCS package: jcs
    try:
        import jcs  # type: ignore

        # PyPI "jcs" exposes canonicalize() and returns bytes.
        out = jcs.canonicalize(obj)  # type: ignore[attr-defined]
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


def canonical_json_bytes(obj: Any, *, allow_non_rfc8785_fallback: bool = False) -> bytes:
    """
    Canonical JSON bytes (Orket RFC-8785 profile):
      - Validate Orket number domain (integer-only, 53-bit safe)
      - Canonicalize using RFC 8785 (JCS)
      - Return UTF-8 bytes of the canonical JSON text
      - No BOM, no trailing newline (canonicalizers should already comply)

    If allow_non_rfc8785_fallback=True, will fall back to legacy Python json.dumps() behavior.
    (Not recommended; use only as a temporary bridge while wiring deps/tests.)
    """
    _validate_orket_number_domain(obj)

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