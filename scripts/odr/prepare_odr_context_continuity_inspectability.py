from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_inspectability import build_inspectability_payload
from scripts.odr.context_continuity_lane import load_lane_config, resolve_lane_artifact_path


def prepare_lane_inspectability(
    *,
    inspectability_input_path: Path,
    config_path: Path | None = None,
    out_path: Path | None = None,
) -> dict[str, object]:
    config = load_lane_config(config_path)
    payload = json.loads(inspectability_input_path.read_text(encoding="utf-8"))
    target_path = out_path or resolve_lane_artifact_path(config, "inspectability_output")
    persisted = build_inspectability_payload(config, payload)
    persisted["inspectability_input_path"] = str(inspectability_input_path.resolve())
    persisted["artifact_locations"]["inspectability_output"] = str(target_path)
    return write_payload_with_diff_ledger(target_path, persisted)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit ContextContinuity per-round inspectability artifacts.")
    parser.add_argument("--input", required=True, help="Path to the inspectability input fixture or harness payload.")
    parser.add_argument("--config", help="Optional lane config override path.")
    parser.add_argument("--out", help="Optional output path override.")
    args = parser.parse_args()

    persisted = prepare_lane_inspectability(
        inspectability_input_path=Path(args.input).resolve(),
        config_path=Path(args.config).resolve() if args.config else None,
        out_path=Path(args.out).resolve() if args.out else None,
    )

    print(
        "Prepared ContextContinuity inspectability artifact "
        f"for {len(persisted['scenario_run_artifacts'])} scenario-runs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
