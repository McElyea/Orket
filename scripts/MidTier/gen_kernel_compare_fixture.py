#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _payload() -> dict:
    return {
        "run_a": {
            "run_id": "sess-generated-a",
            "contract_version": "kernel_api/v1",
            "schema_version": "v1",
            "turn_digests": [
                {
                    "turn_id": "turn-0001",
                    "turn_result_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ],
            "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
            "issues": [],
            "events": ["[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] promoted |"],
            "trace_dir": "C:/agent/observability/sess-generated-a/ISSUE-1/001_developer",
        },
        "run_b": {
            "run_id": "sess-generated-b",
            "contract_version": "kernel_api/v1",
            "schema_version": "v1",
            "turn_digests": [
                {
                    "turn_id": "turn-0001",
                    "turn_result_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                }
            ],
            "stage_outcomes": [{"turn_id": "turn-0001", "stage": "promotion", "outcome": "PASS"}],
            "issues": [],
            "events": ["[INFO] [STAGE:promotion] [CODE:I_PROMOTION_PASS] [LOC:/turn-0001] promoted host-b |"],
            "trace_dir": "/tmp/agent/observability/sess-generated-b/ISSUE-1/001_developer",
        },
        "compare_mode": "structural_parity",
        "expect_outcome": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a kernel compare API fixture payload.")
    parser.add_argument("--out", required=True, help="Output JSON file path.")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_payload(), indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] wrote fixture: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
