from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


def build_security_compat_warnings(*, catalog_payload: dict[str, Any]) -> dict[str, Any]:
    warnings: list[dict[str, Any]] = []
    rows = list(catalog_payload.get("extensions", []))
    for row in rows:
        extension_id = str(row.get("extension_id", "")).strip()
        mode = str(row.get("security_mode", "")).strip() or "compat"
        profile = str(row.get("security_profile", "")).strip() or "production"
        source_ref = str(row.get("source_ref", "")).strip() or "HEAD"
        for fallback_code in list(row.get("compat_fallbacks", [])):
            code = str(fallback_code or "").strip()
            if not code:
                continue
            warnings.append(
                {
                    "event_name": "security_compat_fallback_used",
                    "component": "extensions.manager",
                    "fallback_code": code,
                    "mode": mode,
                    "reason": "catalog_registered",
                    "input_ref": f"{extension_id}@{source_ref}",
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "security_profile": profile,
                }
            )

    warnings.sort(key=lambda row: (row["input_ref"], row["fallback_code"], row["mode"]))
    return {
        "ok": len(warnings) == 0,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Security Compat Warnings",
        "",
        f"- ok: `{str(result['ok']).lower()}`",
        f"- warning_count: `{result['warning_count']}`",
        "",
    ]
    warnings = list(result.get("warnings", []))
    if not warnings:
        lines.append("No compatibility fallback warnings detected.")
        lines.append("")
        return "\n".join(lines)
    lines.append("| input_ref | fallback_code | mode | reason |")
    lines.append("|---|---|---|---|")
    for row in warnings:
        lines.append(f"| `{row['input_ref']}` | `{row['fallback_code']}` | `{row['mode']}` | `{row['reason']}` |")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export compatibility fallback warning artifacts for CI.")
    parser.add_argument("--catalog", default=".orket/durable/config/extensions_catalog.json")
    parser.add_argument("--out-json", default="benchmarks/results/security/security_compat_warnings.json")
    parser.add_argument("--out-md", default="benchmarks/results/security/security_compat_warnings.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_payload = _load_catalog(Path(args.catalog))
    result = build_security_compat_warnings(catalog_payload=catalog_payload)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
