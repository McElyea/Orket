from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render markdown digest for explorer checks.")
    parser.add_argument("--summary", required=True, help="Path to explorer_check_summary.json")
    parser.add_argument("--out", required=True, help="Path to markdown digest")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    summary = _load(Path(args.summary))
    execution_lane = str(summary.get("execution_lane") or "").strip()
    vram_profile = str(summary.get("vram_profile") or "").strip()
    provenance_ref = str(summary.get("provenance_ref") or "").strip()
    missing = []
    if not execution_lane:
        missing.append("execution_lane")
    if not vram_profile:
        missing.append("vram_profile")
    if not provenance_ref:
        missing.append("provenance_ref")
    if missing:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "MISSING_SUMMARY_PROVENANCE_FIELDS",
                    "missing": missing,
                },
                indent=2,
            )
        )
        return 2

    statuses = summary.get("statuses") if isinstance(summary.get("statuses"), dict) else {}
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    lines = [
        "# Explorer Check Digest",
        "",
        f"- overall_status: `{str(summary.get('status') or 'UNKNOWN')}`",
        f"- execution_lane: `{execution_lane}`",
        f"- vram_profile: `{vram_profile}`",
        f"- provenance_ref: `{provenance_ref}`",
        "",
        "| Check | Status | Artifact |",
        "| --- | --- | --- |",
    ]
    for key in ["ingestion", "rollup", "guards"]:
        lines.append(
            f"| {key} | {str(statuses.get(key) or 'UNKNOWN')} | `{str(artifacts.get(key) or '')}` |"
        )
    lines.append("")
    failed = summary.get("failed_checks") if isinstance(summary.get("failed_checks"), list) else []
    if failed:
        lines.append("## Failed Checks")
        for item in failed:
            lines.append(f"- `{str(item)}`")
        lines.append("")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "OK", "out": str(out_path).replace("\\", "/")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
