#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


CODE_RE = re.compile(r"`([EI]_[A-Z0-9_]+)`")
TOKEN_RE = re.compile(r"^[EI]_[A-Z0-9_]+$")


def _load_registry(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("codes"), list):
        raise ValueError("registry payload must contain list field 'codes'")
    codes = [code for code in payload["codes"] if isinstance(code, str)]
    return codes


def _extract_doc_codes(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return {match.group(1) for match in CODE_RE.finditer(text)}


def main() -> int:
    registry_path = Path("docs/projects/OS/contracts/error-codes-v1.json")
    docs_paths = sorted(Path("docs/projects/OS").rglob("*.md"))

    registry_codes = _load_registry(registry_path)
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

    print("[PASS] registry audit passed")
    print(f"[PASS] registry_count={len(registry_codes)} doc_code_count={len(doc_set)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
