from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.application.services.skills_validator import validate_skill_manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Skill manifest contract compliance.")
    parser.add_argument("--manifest", required=True, help="Path to Skill manifest JSON.")
    parser.add_argument("--out", default="", help="Optional output path for report JSON.")
    return parser.parse_args()


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Skill manifest must be a JSON object.")
    return payload


def main() -> int:
    args = _parse_args()
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    validation = validate_skill_manifest(manifest)
    errors = list(validation.get("errors") or [])

    report = {
        "status": "PASS" if validation.get("contract_valid") is True and not errors else "FAIL",
        "manifest": str(manifest_path).replace("\\", "/"),
        "skill_id": str(manifest.get("skill_id") or "unknown"),
        "skill_version": str(manifest.get("skill_version") or "unknown"),
        "validation": validation,
        "failures": errors,
    }
    text = json.dumps(report, indent=2)
    print(text)

    out_path_text = str(args.out or "").strip()
    if out_path_text:
        out_path = Path(out_path_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")

    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
