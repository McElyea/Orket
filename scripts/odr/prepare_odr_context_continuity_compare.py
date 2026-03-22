from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_compare import (
    build_context_continuity_compare_payload,
    resolve_default_compare_output_path,
)


def prepare_context_continuity_compare(
    *,
    compare_input_path: Path,
    config_path: Path | None = None,
    out_path: Path | None = None,
) -> dict[str, object]:
    payload = build_context_continuity_compare_payload(compare_input_path, config_path=config_path)
    target_path = out_path or resolve_default_compare_output_path(config_path)
    return write_payload_with_diff_ledger(target_path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit ContextContinuity control, V0, and V1 compare payloads.")
    parser.add_argument("--input", required=True, help="Path to the compare input fixture or harness payload.")
    parser.add_argument("--config", help="Optional lane config override path.")
    parser.add_argument("--out", help="Optional output path override.")
    args = parser.parse_args()

    persisted = prepare_context_continuity_compare(
        compare_input_path=Path(args.input).resolve(),
        config_path=Path(args.config).resolve() if args.config else None,
        out_path=Path(args.out).resolve() if args.out else None,
    )
    print(
        "Prepared ContextContinuity compare artifact "
        f"for {len(persisted['scenario_runs'])} scenario-runs and {len(persisted['budget_verdicts'])} budget verdicts."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
