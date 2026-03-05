from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.summarize_protocol_error_codes import main


def test_summarize_protocol_error_codes_reports_family_distribution(tmp_path: Path) -> None:
    payload = {
        "errors": [
            {"error_code": "E_PARSE_JSON"},
            {"error_code": "E_WORKSPACE_CONSTRAINT:path_traversal"},
            {"code": "E_WORKSPACE_CONSTRAINT:absolute_path"},
            {"error_code": "E_UNKNOWN_CUSTOM"},
        ]
    }
    report = tmp_path / "input.json"
    out = tmp_path / "summary.json"
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    exit_code = main(["--input", str(report), "--out", str(out)])
    assert exit_code == 0

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["total_codes"] == 4
    assert summary["family_counts"]["E_PARSE_JSON"] == 1
    assert summary["family_counts"]["E_WORKSPACE_CONSTRAINT"] == 2
    assert summary["family_counts"]["UNREGISTERED"] == 1
    assert summary["unregistered_codes"]["E_UNKNOWN_CUSTOM"] == 1


def test_summarize_protocol_error_codes_strict_fails_on_unregistered_codes(tmp_path: Path) -> None:
    report = tmp_path / "input.jsonl"
    report.write_text(
        "\n".join(
            [
                json.dumps({"error_code": "E_PARSE_JSON"}),
                json.dumps({"error_code": "E_UNKNOWN_CUSTOM"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["--input", str(report), "--strict"])
    assert exit_code == 1

