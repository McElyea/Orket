from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.protocol_error_codes import error_family, is_registered_protocol_error_code


ERROR_KEYS = {"error_code", "code"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize protocol error code usage and family distribution for dashboard ingestion.",
    )
    parser.add_argument("--input", action="append", required=True, help="Input JSON/JSONL path (repeatable).")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when unregistered protocol codes are detected.")
    return parser


def _append_count(counter: dict[str, int], key: str) -> None:
    normalized = str(key or "").strip()
    if not normalized:
        return
    counter[normalized] = int(counter.get(normalized, 0)) + 1


def _walk_codes(node: Any, collected: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ERROR_KEYS and isinstance(value, str) and value.strip().startswith("E_"):
                collected.append(value.strip())
            _walk_codes(value, collected)
        return
    if isinstance(node, list):
        for item in node:
            if isinstance(item, str) and item.strip().startswith("E_"):
                collected.append(item.strip())
            else:
                _walk_codes(item, collected)
        return


def _load_json_or_jsonl(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows: list[Any] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
        return rows
    return json.loads(text)


def _sorted_counts(counter: dict[str, int]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def summarize_protocol_error_codes(paths: list[Path]) -> dict[str, Any]:
    codes: list[str] = []
    for path in paths:
        _walk_codes(_load_json_or_jsonl(path), codes)

    exact_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    unregistered_codes: dict[str, int] = {}

    for code in codes:
        _append_count(exact_counts, code)
        family = error_family(code) or "UNREGISTERED"
        _append_count(family_counts, family)
        if not is_registered_protocol_error_code(code):
            _append_count(unregistered_codes, code)

    total_codes = len(codes)
    unregistered_count = sum(unregistered_codes.values())
    registered_count = total_codes - unregistered_count

    return {
        "input_count": len(paths),
        "total_codes": total_codes,
        "registered_count": registered_count,
        "unregistered_count": unregistered_count,
        "family_counts": _sorted_counts(family_counts),
        "exact_counts": _sorted_counts(exact_counts),
        "unregistered_codes": _sorted_counts(unregistered_codes),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = [Path(str(raw)).resolve() for raw in list(args.input or [])]
    payload = summarize_protocol_error_codes(paths)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    out_raw = str(args.out or "").strip()
    if out_raw:
        out_path = Path(out_raw).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    if bool(args.strict) and int(payload.get("unregistered_count") or 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

