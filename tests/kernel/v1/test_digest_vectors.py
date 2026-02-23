from __future__ import annotations

import base64
import json
from pathlib import Path

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


def test_digest_vectors_parity() -> None:
    vectors_path = Path("tests/kernel/v1/vectors/digest-v1.json")
    payload = json.loads(vectors_path.read_text(encoding="utf-8"))

    assert payload["version"] == "digest-v1"
    assert payload["algorithm"] == "sha256"
    assert isinstance(payload.get("vectors"), list)

    for vector in payload["vectors"]:
        if "input" in vector:
            canonical = canonical_json_bytes(vector["input"]).decode("utf-8")
            digest_hex = structural_digest(canonical.encode("utf-8"))
            assert canonical == vector["canonical"], f"canonical mismatch for vector={vector['name']}"
            assert digest_hex == vector["digest_hex"], f"digest mismatch for vector={vector['name']}"
            continue

        if "raw_utf8" in vector:
            raw = vector["raw_utf8"].encode("utf-8")
        else:
            raw = base64.b64decode(vector["raw_b64"])
        actual_error = _classify_raw_bytes(raw)
        assert actual_error == vector["expect_error"], f"error mismatch for vector={vector['name']}"

