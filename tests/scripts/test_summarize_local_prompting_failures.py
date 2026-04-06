# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.summarize_local_prompting_failures import main


def test_summarize_local_prompting_failures_aggregates_families(tmp_path: Path) -> None:
    input_a = tmp_path / "a.json"
    input_b = tmp_path / "b.json"
    out = tmp_path / "summary.json"
    input_a.write_text(
        json.dumps(
            {
                "schema_version": "local_prompting_conformance.strict_json.v1",
                "profile_id": "p1",
                "task_class": "strict_json",
                "total_cases": 10,
                "pass_cases": 8,
                "failure_families": {"ERR_JSON_MD_FENCE": 2},
            }
        ),
        encoding="utf-8",
    )
    input_b.write_text(
        json.dumps(
            {
                "schema_version": "local_prompting_conformance.tool_call.v1",
                "profile_id": "p1",
                "task_class": "tool_call",
                "total_cases": 5,
                "pass_cases": 4,
                "failure_families": {"SCHEMA_MISMATCH": 1},
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--input", str(input_a), "--input", str(input_b), "--out", str(out), "--strict"])
    assert exit_code == 1

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["total_failures"] == 3
    assert payload["family_counts"]["EXTRANEOUS_TEXT"] == 2
    assert payload["family_counts"]["SCHEMA_MISMATCH"] == 1
