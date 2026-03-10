from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.runtime_config_ownership_map import (
    runtime_config_ownership_map_snapshot,
    validate_runtime_config_ownership_map,
)

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - script execution fallback
    import importlib.util

    helper_path = Path(__file__).resolve().parents[1] / "common" / "rerun_diff_ledger.py"
    spec = importlib.util.spec_from_file_location("rerun_diff_ledger", helper_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"E_DIFF_LEDGER_HELPER_LOAD_FAILED:{helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    write_payload_with_diff_ledger = module.write_payload_with_diff_ledger


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check runtime config ownership map contract.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args(argv)


def evaluate_runtime_config_ownership_map() -> dict[str, Any]:
    snapshot = runtime_config_ownership_map_snapshot()
    try:
        config_keys = list(validate_runtime_config_ownership_map())
    except ValueError as exc:
        return {
            "schema_version": "1.0",
            "ok": False,
            "error": str(exc),
            "snapshot": snapshot,
        }

    return {
        "schema_version": "1.0",
        "ok": True,
        "config_key_count": len(config_keys),
        "config_keys": config_keys,
        "snapshot": snapshot,
    }


def check_runtime_config_ownership_map(*, out_path: Path | None = None) -> tuple[int, dict[str, Any]]:
    payload = evaluate_runtime_config_ownership_map()
    if out_path is not None:
        write_payload_with_diff_ledger(out_path, payload)
    return (0 if bool(payload.get("ok")) else 1), payload


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    out_path = Path(args.out).resolve() if str(args.out or "").strip() else None
    exit_code, payload = check_runtime_config_ownership_map(out_path=out_path)
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
