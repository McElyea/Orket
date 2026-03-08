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

from orket.runtime.controller_replay_parity import compare_controller_replay_outputs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two controller run outputs for replay/parity equivalence.",
    )
    parser.add_argument("--expected", required=True, help="Path to expected run payload JSON.")
    parser.add_argument("--actual", required=True, help="Path to actual run payload JSON.")
    parser.add_argument("--out", default="", help="Optional output JSON report path.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when parity does not match.")
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _extract_controller_output(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("controller_summary"), dict):
        return payload
    output = payload.get("output")
    if isinstance(output, dict) and isinstance(output.get("controller_summary"), dict):
        return output
    summary = payload.get("summary")
    if isinstance(summary, dict):
        nested_output = summary.get("output")
        if isinstance(nested_output, dict) and isinstance(nested_output.get("controller_summary"), dict):
            return nested_output
    raise ValueError("payload missing controller output shape")


def _write_report(report: dict[str, Any], out_path: Path | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if out_path is None:
        print(text, end="")
        return
    write_payload_with_diff_ledger(out_path, report)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    expected_payload = _load_json(Path(str(args.expected)).resolve())
    actual_payload = _load_json(Path(str(args.actual)).resolve())
    report = compare_controller_replay_outputs(
        expected_output=_extract_controller_output(expected_payload),
        actual_output=_extract_controller_output(actual_payload),
    )
    out_raw = str(args.out or "").strip()
    _write_report(report, Path(out_raw).resolve() if out_raw else None)
    if bool(args.strict) and not bool(report.get("parity_ok", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
