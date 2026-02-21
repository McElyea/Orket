from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract stability KPI block from quant sweep summary.")
    parser.add_argument("--summary", required=True, help="Path to sweep_summary.json")
    parser.add_argument("--out", required=True, help="Path to write KPI report JSON")
    return parser.parse_args()


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Sweep summary must be a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    summary = _load_summary(Path(args.summary))
    kpis = summary.get("stability_kpis") if isinstance(summary.get("stability_kpis"), dict) else {}
    out_payload = {
        "summary_path": str(Path(args.summary)).replace("\\", "/"),
        "stability_kpis": kpis,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out_payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
