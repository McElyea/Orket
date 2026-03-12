# Layer: contract

from __future__ import annotations

import json
from pathlib import Path

from scripts.gitea.run_local_runner_lifecycle_proof import _build_parser, main


def test_parser_defaults_target_existing_local_workflow() -> None:
    args = _build_parser().parse_args([])

    assert args.workflow_id == "monorepo-packages-ci.yml"
    assert args.allowed_container == ["vibe-rail-gitea"]
    assert args.out == "benchmarks/results/gitea/local_runner_lifecycle_proof.json"


def test_main_writes_diff_ledger_report(tmp_path: Path, monkeypatch) -> None:
    async def fake_run_proof(_args):
        return (
            0,
            {
                "schema_version": "gitea.local_runner_lifecycle_proof.v1",
                "status": "success",
                "workflow_id": "monorepo-packages-ci.yml",
                "run": {"run_id": 42, "attempts": [{"attempt_number": 1}], "conclusion": "success"},
            },
        )

    monkeypatch.setattr("scripts.gitea.run_local_runner_lifecycle_proof._run_proof", fake_run_proof)

    out_path = tmp_path / "benchmarks" / "results" / "gitea" / "proof.json"
    exit_code = main(["--repo-root", str(tmp_path), "--out", str(out_path.relative_to(tmp_path))])

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "success"
    assert payload["run"]["run_id"] == 42
    assert "diff_ledger" in payload
