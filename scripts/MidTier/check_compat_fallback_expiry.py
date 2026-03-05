from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket import __version__ as orket_version
from orket.extensions.compat_fallback_registry import compat_fallback_codes, iter_compat_fallback_rules
from orket.extensions.models import default_extensions_catalog_path


def _parse_semver(value: str) -> tuple[int, int, int]:
    match = re.match(r"^\s*(\d+)\.(\d+)\.(\d+)", str(value or ""))
    if not match:
        raise ValueError(f"invalid_semver: {value}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


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


def evaluate_compat_fallback_expiry(*, current_version: str, catalog_payload: dict[str, Any]) -> dict[str, Any]:
    rules = list(iter_compat_fallback_rules())
    allowed_codes = compat_fallback_codes()
    observed_codes: set[str] = set()
    unknown_codes: set[str] = set()
    for row in list(catalog_payload.get("extensions", [])):
        for code in list(row.get("compat_fallbacks", [])):
            normalized = str(code or "").strip()
            if not normalized:
                continue
            observed_codes.add(normalized)
            if normalized not in allowed_codes:
                unknown_codes.add(normalized)

    expired_active: list[dict[str, str]] = []
    active_rules: list[dict[str, str]] = []
    for rule in rules:
        active = rule.fallback_code in observed_codes
        if active:
            active_rules.append(
                {
                    "fallback_code": rule.fallback_code,
                    "introduced_in": rule.introduced_in,
                    "expiry_version": rule.expiry_version,
                    "removal_phase": rule.removal_phase,
                }
            )
            if _version_gte(current_version, rule.expiry_version):
                expired_active.append(
                    {
                        "fallback_code": rule.fallback_code,
                        "expiry_version": rule.expiry_version,
                        "current_version": current_version,
                        "removal_phase": rule.removal_phase,
                    }
                )

    result = {
        "ok": len(expired_active) == 0 and len(unknown_codes) == 0,
        "current_version": current_version,
        "registry_size": len(rules),
        "observed_codes": sorted(observed_codes),
        "active_rules": active_rules,
        "expired_active": expired_active,
        "unknown_codes": sorted(unknown_codes),
    }
    return result


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Security Compat Fallback Expiry Check",
        "",
        f"- current_version: `{result['current_version']}`",
        f"- ok: `{str(result['ok']).lower()}`",
        f"- registry_size: `{result['registry_size']}`",
        "",
        "## Observed Codes",
    ]
    observed = list(result.get("observed_codes", []))
    if observed:
        for code in observed:
            lines.append(f"- `{code}`")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Expired Active")
    expired = list(result.get("expired_active", []))
    if expired:
        for row in expired:
            lines.append(
                f"- `{row['fallback_code']}` expired at `{row['expiry_version']}` (current `{row['current_version']}`)"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Unknown Codes")
    unknown = list(result.get("unknown_codes", []))
    if unknown:
        for code in unknown:
            lines.append(f"- `{code}`")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail CI when expired compatibility fallbacks remain active.")
    parser.add_argument("--catalog", default=str(default_extensions_catalog_path()))
    parser.add_argument("--current-version", default=orket_version)
    parser.add_argument("--out-json", default="benchmarks/results/security_compat_expiry_check.json")
    parser.add_argument("--out-md", default="benchmarks/results/security_compat_expiry_check.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_payload = _load_catalog(Path(args.catalog))
    result = evaluate_compat_fallback_expiry(
        current_version=str(args.current_version),
        catalog_payload=catalog_payload,
    )
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
