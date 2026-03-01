#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import hashlib
from pathlib import Path


CODE_RE = re.compile(r"`([EI]_[A-Z0-9_]+)`")
TOKEN_RE = re.compile(r"^[EI]_[A-Z0-9_]+$")
CONTRACTS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28/contracts")
DOCS_ROOT = Path("docs/projects/archive/OS-Stale-2026-02-28")


def _canonical_json_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _load_registry(path: Path) -> tuple[list[str], dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("registry payload must be an object")

    codes = payload.get("codes")
    if isinstance(codes, list):
        code_list = [code for code in codes if isinstance(code, str)]
        wrapper = {
            "contract_version": "os/v1",
            "codes": {code: {"kind": "error" if code.startswith("E_") else "info"} for code in code_list},
        }
        return code_list, wrapper

    if isinstance(codes, dict):
        code_list = [code for code in codes.keys() if isinstance(code, str)]
        wrapper = payload
        return code_list, wrapper

    raise ValueError("registry payload must contain 'codes' as object (preferred) or list (legacy)")


def _extract_doc_codes(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(1) for match in CODE_RE.finditer(text)}


def main() -> int:
    registry_path = CONTRACTS_ROOT / "error-codes-v1.json"
    docs_paths = sorted(DOCS_ROOT.rglob("*.md"))

    registry_codes, registry_wrapper = _load_registry(registry_path)
    registry_set = set(registry_codes)
    doc_set: set[str] = set()
    for path in docs_paths:
        doc_set |= _extract_doc_codes(path)

    errors: list[str] = []

    # Registry integrity.
    duplicates = sorted({code for code in registry_codes if registry_codes.count(code) > 1})
    if duplicates:
        errors.append(f"duplicate_codes={duplicates}")

    unsorted = registry_codes != sorted(registry_codes)
    if unsorted:
        errors.append("registry_codes_not_sorted=true")

    invalid_pattern = sorted(code for code in registry_codes if not TOKEN_RE.fullmatch(code))
    if invalid_pattern:
        errors.append(f"invalid_pattern_codes={invalid_pattern}")

    # Truth triangle strict side: docs -> registry.
    missing_in_registry = sorted(doc_set - registry_set)
    if missing_in_registry:
        errors.append(f"missing_in_registry={missing_in_registry}")

    # Visibility side: registry extras fail closed (all active codes must be documented).
    extra_in_registry = sorted(registry_set - doc_set)
    if extra_in_registry:
        errors.append(f"extra_in_registry={extra_in_registry}")

    if errors:
        print("[FAIL] registry audit failed")
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    wrapper_digest = hashlib.sha256(_canonical_json_bytes(registry_wrapper)).hexdigest()
    print("[PASS] registry audit passed")
    print(f"[PASS] registry_count={len(registry_codes)} doc_code_count={len(doc_set)}")
    print(f"[PASS] registry_digest_sha256={wrapper_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
