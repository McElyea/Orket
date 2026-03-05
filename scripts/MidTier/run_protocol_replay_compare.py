from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.runtime.protocol_replay import ProtocolReplayEngine


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare protocol-governed replay state for two run ledgers.",
    )
    parser.add_argument("--run-a-events", required=True, help="Path to run A events.log")
    parser.add_argument("--run-b-events", required=True, help="Path to run B events.log")
    parser.add_argument("--run-a-artifacts", default="", help="Optional path to run A artifact root")
    parser.add_argument("--run-b-artifacts", default="", help="Optional path to run B artifact root")
    parser.add_argument("--run-a-receipts", default="", help="Optional path to run A receipts.log")
    parser.add_argument("--run-b-receipts", default="", help="Optional path to run B receipts.log")
    parser.add_argument("--out", default="", help="Optional output JSON path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when deterministic_match is false.",
    )
    return parser


def _resolve_optional_path(raw: str) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    return Path(value).resolve()


def _run_compare(args: argparse.Namespace) -> dict[str, Any]:
    engine = ProtocolReplayEngine()
    run_a_events = Path(str(args.run_a_events)).resolve()
    run_b_events = Path(str(args.run_b_events)).resolve()
    run_a_artifacts = _resolve_optional_path(str(args.run_a_artifacts))
    run_b_artifacts = _resolve_optional_path(str(args.run_b_artifacts))
    run_a_receipts = _resolve_optional_path(str(args.run_a_receipts))
    run_b_receipts = _resolve_optional_path(str(args.run_b_receipts))
    return engine.compare_replays(
        run_a_events_path=run_a_events,
        run_b_events_path=run_b_events,
        run_a_artifact_root=run_a_artifacts,
        run_b_artifact_root=run_b_artifacts,
        run_a_receipts_path=run_a_receipts,
        run_b_receipts_path=run_b_receipts,
    )


def _write_output(payload: dict[str, Any], out_path: Path | None) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if out_path is None:
        print(text, end="")
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = _run_compare(args)
    out_path = _resolve_optional_path(str(args.out))
    _write_output(payload, out_path)
    if bool(args.strict) and not bool(payload.get("deterministic_match", False)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
