from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.odr.context_continuity_lane import (
    DEFAULT_LANE_CONFIG_PATH,
    build_bootstrap_payload,
    load_lane_config,
    resolve_default_output_path,
)


def prepare_lane_bootstrap(*, config_path: Path, out_path: Path | None = None) -> dict:
    config = load_lane_config(config_path)
    payload = build_bootstrap_payload(config)
    target_path = out_path or resolve_default_output_path(config)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    return write_payload_with_diff_ledger(target_path, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the locked ODR context continuity lane bootstrap artifact.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_LANE_CONFIG_PATH),
        help="Lane config JSON path.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path override. Empty uses the config's canonical bootstrap path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = Path(args.config).resolve()
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    persisted = prepare_lane_bootstrap(config_path=config_path, out_path=out_path)
    print(
        "Prepared ODR context continuity lane bootstrap: "
        f"scope={persisted['execution_scope']['evidence_scope']} "
        f"pairs={len(persisted['execution_scope']['selected_primary_pairs'])} "
        f"budgets={persisted['execution_scope']['locked_budgets']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
