from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VOLATILE_TOP_LEVEL_FIELDS = {"recorded_at", "artifact_id"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two replay artifacts for deterministic drift.")
    parser.add_argument("--left", required=True, help="Left replay artifact JSON path.")
    parser.add_argument("--right", required=True, help="Right replay artifact JSON path.")
    parser.add_argument("--out", default="", help="Optional output path for comparison report.")
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_value(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=False)
    if len(rendered) > 160:
        return rendered[:157] + "..."
    return rendered


def _compare_values(*, left: Any, right: Any, path: str, mismatches: list[dict[str, str]]) -> None:
    if type(left) is not type(right):
        mismatches.append(
            {
                "field": path,
                "reason": "type_mismatch",
                "left": type(left).__name__,
                "right": type(right).__name__,
            }
        )
        return

    if isinstance(left, dict):
        left_keys = set(left.keys())
        right_keys = set(right.keys())
        all_keys = sorted(left_keys | right_keys)
        for key in all_keys:
            if not path and key in VOLATILE_TOP_LEVEL_FIELDS:
                continue
            key_path = f"{path}.{key}" if path else key
            if key not in left:
                mismatches.append({"field": key_path, "reason": "missing_left", "left": "<missing>", "right": "present"})
                continue
            if key not in right:
                mismatches.append({"field": key_path, "reason": "missing_right", "left": "present", "right": "<missing>"})
                continue
            _compare_values(left=left[key], right=right[key], path=key_path, mismatches=mismatches)
        return

    if isinstance(left, list):
        if len(left) != len(right):
            mismatches.append(
                {
                    "field": path,
                    "reason": "length_mismatch",
                    "left": str(len(left)),
                    "right": str(len(right)),
                }
            )
            return
        for idx, (left_item, right_item) in enumerate(zip(left, right)):
            item_path = f"{path}[{idx}]"
            _compare_values(left=left_item, right=right_item, path=item_path, mismatches=mismatches)
        return

    if left != right:
        mismatches.append(
            {
                "field": path,
                "reason": "value_mismatch",
                "left": _format_value(left),
                "right": _format_value(right),
            }
        )


def main() -> int:
    args = _parse_args()
    left_path = Path(args.left)
    right_path = Path(args.right)
    left_payload = _load_json(left_path)
    right_payload = _load_json(right_path)
    if not isinstance(left_payload, dict) or not isinstance(right_payload, dict):
        raise SystemExit("left and right replay artifacts must be JSON objects")

    mismatches: list[dict[str, str]] = []
    _compare_values(left=left_payload, right=right_payload, path="", mismatches=mismatches)
    mismatches = sorted(mismatches, key=lambda item: (item.get("field", ""), item.get("reason", "")))

    summary = [f"{item['field']}: {item['reason']}" for item in mismatches]
    report = {
        "status": "PASS" if not mismatches else "FAIL",
        "left": str(left_path).replace("\\", "/"),
        "right": str(right_path).replace("\\", "/"),
        "mismatch_count": len(mismatches),
        "summary": summary,
        "mismatches": mismatches,
    }

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    out_text = str(args.out or "").strip()
    if out_text:
        out_path = Path(out_text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
