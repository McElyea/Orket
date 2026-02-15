from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.application.services.canonical_role_templates import (
    CANONICAL_PIPELINE_ROLES,
    normalize_canonical_role_payload,
)


def _role_path(root: Path, role_name: str) -> Path:
    return root / "model" / "core" / "roles" / f"{role_name}.json"


def _load_json(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_json(payload: Dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _drifted_roles(root: Path) -> List[tuple[Path, str]]:
    drift: List[tuple[Path, str]] = []
    for role_name in CANONICAL_PIPELINE_ROLES:
        path = _role_path(root, role_name)
        if not path.exists():
            raise FileNotFoundError(f"Missing canonical role asset: {path}")
        current_payload = _load_json(path)
        normalized = normalize_canonical_role_payload(role_name, current_payload)
        rendered = _format_json(normalized)
        if path.read_text(encoding="utf-8") != rendered:
            drift.append((path, rendered))
    return drift


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate canonical role structure templates.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--apply", action="store_true", help="Write normalized role templates to disk.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    drift = _drifted_roles(root)

    if not drift:
        print("Canonical role templates already up to date.")
        return 0

    if not args.apply:
        print("Canonical role template drift detected:")
        for path, _ in drift:
            print(f"- {path}")
        print("Run with --apply to regenerate canonical role files.")
        return 1

    for path, rendered in drift:
        path.write_text(rendered, encoding="utf-8")
        print(f"Updated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
