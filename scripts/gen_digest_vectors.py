#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.kernel.v1.canonical import canonical_json_bytes, structural_digest


def _classify_raw_bytes(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "E_DIGEST_INVALID_UTF8"

    if "\r" in text:
        return "E_DIGEST_NORMALIZATION_MISMATCH"
    if not text.endswith("\n"):
        return "E_DIGEST_TRAILING_NEWLINE_REQUIRED"
    if text.endswith("\n\n"):
        return "E_DIGEST_NORMALIZATION_MISMATCH"
    return None


def _object_vector(name: str, value: Any) -> dict[str, Any]:
    canonical = canonical_json_bytes(value).decode("utf-8")
    digest_hex = structural_digest(canonical.encode("utf-8"))
    return {
        "name": name,
        "input": value,
        "canonical": canonical,
        "digest_hex": digest_hex,
    }


def _build_vectors() -> dict[str, Any]:
    vectors: list[dict[str, Any]] = [
        _object_vector("basic-sorted", {"b": 2, "a": 1}),
        _object_vector("unicode-literal", {"m": "🚀"}),
        _object_vector("nested-mix", {"root": [{"z": 2, "a": 1}, {"k": "v"}], "n": 7}),
        _object_vector("safe-int-boundary", {"max_safe": 9007199254740991, "min_safe": -9007199254740991}),
    ]

    for name, raw in (
        ("fail-newline-required", b'{"a":1}'),
        ("fail-crlf", b'{"a":1}\r\n'),
        ("fail-invalid-utf8-lone-continuation", base64.b64decode("gA==")),
    ):
        error = _classify_raw_bytes(raw)
        entry: dict[str, Any] = {"name": name, "expect_error": error}
        try:
            decoded = raw.decode("utf-8")
            entry["raw_utf8"] = decoded
        except UnicodeDecodeError:
            entry["raw_b64"] = base64.b64encode(raw).decode("ascii")
        vectors.append(entry)

    return {
        "version": "digest-v1",
        "algorithm": "sha256",
        "vectors": vectors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate committed digest vectors.")
    parser.add_argument(
        "--out",
        default="tests/kernel/v1/vectors/digest-v1.json",
        help="Output file path for digest vectors.",
    )
    args = parser.parse_args()

    payload = _build_vectors()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote_vectors={out_path.as_posix()} count={len(payload['vectors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
