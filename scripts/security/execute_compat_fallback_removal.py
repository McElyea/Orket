from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket import __version__ as orket_version
from orket.extensions.compat_fallback_registry import iter_compat_fallback_rules
from orket.extensions.models import default_extensions_catalog_path


def _parse_semver(value: str) -> tuple[int, int, int]:
    parts = str(value or "").split(".")
    if len(parts) < 3:
        raise ValueError(f"invalid_semver: {value}")
    major = int(parts[0])
    minor = int(parts[1])
    patch_raw = parts[2]
    patch = int("".join(ch for ch in patch_raw if ch.isdigit()) or "0")
    return (major, minor, patch)


def _version_gte(left: str, right: str) -> bool:
    return _parse_semver(left) >= _parse_semver(right)


def _load_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"extensions": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"extensions": []}
    rows = payload.get("extensions", [])
    if not isinstance(rows, list):
        return {"extensions": []}
    return {"extensions": rows}


def execute_removal(*, catalog_payload: dict[str, Any], current_version: str) -> dict[str, Any]:
    expiry_by_code = {rule.fallback_code: rule.expiry_version for rule in iter_compat_fallback_rules()}
    rows = list(catalog_payload.get("extensions", []))
    removed: list[dict[str, Any]] = []
    changed = False

    for row in rows:
        extension_id = str(row.get("extension_id", "")).strip() or "<unknown>"
        original_codes = [str(code).strip() for code in list(row.get("compat_fallbacks", [])) if str(code).strip()]
        kept_codes: list[str] = []
        for code in original_codes:
            expiry = expiry_by_code.get(code)
            if expiry and _version_gte(current_version, expiry):
                removed.append(
                    {
                        "extension_id": extension_id,
                        "fallback_code": code,
                        "expiry_version": expiry,
                        "current_version": current_version,
                    }
                )
                changed = True
                continue
            kept_codes.append(code)
        row["compat_fallbacks"] = kept_codes

    return {
        "ok": True,
        "changed": changed,
        "current_version": current_version,
        "removed_count": len(removed),
        "removed": removed,
        "catalog": {"extensions": rows},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute compatibility fallback removal for expired fallbacks.")
    parser.add_argument("--catalog", default=str(default_extensions_catalog_path()))
    parser.add_argument("--current-version", default=orket_version)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--out-json", default="benchmarks/results/security/security_compat_removal_execution.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_path = Path(args.catalog)
    loaded = _load_catalog(catalog_path)
    result = execute_removal(catalog_payload=loaded, current_version=str(args.current_version))
    if args.write and result.get("changed", False):
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_path.write_text(json.dumps(result["catalog"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_json = Path(args.out_json)
    write_payload_with_diff_ledger(out_json, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
