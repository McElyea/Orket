# LIFECYCLE: live
# Layer: contract

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.benchmarks import run_local_model_coding_challenge as script


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_summarize_run_extracts_first_code_turn_and_blocker_note(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_json(
        workspace / "runs" / "run-001" / "run_summary.json",
        {
            "run_id": "run-001",
            "status": "terminal_failure",
            "duration_ms": 1234,
            "failure_reason": "terminal_failure",
            "tools_used": [],
            "artifact_ids": [],
            "stop_reason": "terminal_failure",
            "cards_runtime": {
                "repair_ledger": {
                    "entries": [
                        {
                            "issue_id": "CWR-01",
                            "turn_index": 1,
                            "reasons": ["artifact_semantic_contract_not_met"],
                        },
                        {
                            "issue_id": "CWR-04",
                            "turn_index": 8,
                            "reasons": ["artifact_semantic_contract_not_met"],
                        },
                    ],
                    "final_disposition": "accepted_with_repair",
                    "repair_count": 3,
                },
            },
        },
    )
    _write_json(
        workspace / "observability" / "run-001" / "cwr-03" / "005_coder" / "parsed_tool_calls.json",
        [
            {
                "tool": "write_file",
                "args": {
                    "path": "agent_output/challenge_inputs/workflow_valid.json",
                    "content": "{\"workflow_id\": \"wf_v\"}",
                },
            }
        ],
    )
    _write_json(
        workspace / "observability" / "run-001" / "cwr-04" / "007_coder" / "parsed_tool_calls.json",
        [
            {
                "tool": "write_file",
                "args": {
                    "path": "agent_output/challenge_runtime/models.py",
                    "content": "class WorkflowSpec: ...",
                },
            }
        ],
    )
    _write_json(
        workspace / "observability" / "run-001" / "cwr-04" / "008_coder" / "messages.json",
        [
            {
                "role": "user",
                "content": (
                    "Issue Brief:\n"
                    "Retry Note: runtime_guard_retry_scheduled: runtime stdout assertion failed: "
                    "path=workflow_id op=eq expected='valid_workflow' actual='wf_v'"
                ),
            }
        ],
    )
    (workspace / "agent_output" / "challenge_runtime").mkdir(parents=True, exist_ok=True)
    (workspace / "agent_output" / "challenge_runtime" / "__init__.py").write_text(
        "from .models import WorkflowSpec\n",
        encoding="utf-8",
    )
    (workspace / "agent_output" / "challenge_runtime" / "models.py").write_text(
        "class WorkflowSpec(dict):\n    pass\n",
        encoding="utf-8",
    )

    run = script._summarize_run(
        repo_root=tmp_path,
        workspace=workspace,
        epic="challenge_workflow_runtime",
        provider="lmstudio",
        model="google/gemma-4-26b-a4b",
        run_ordinal=1,
        execution={"command": ["python", "main.py"], "exit_code": 1, "stdout": "", "stderr": ""},
    )

    assert run["deepest_issue"] == "CWR-04"
    assert run["first_artifact_write"]["turn_index"] == 5
    assert run["first_program_write"]["turn_index"] == 7
    assert run["challenge_runtime_py_files"] == ["challenge_runtime/models.py"]
    assert run["repair_count"] == 3
    assert run["final_disposition"] == "accepted_with_repair"
    assert run["final_blocker_family"] == "runtime_stdout_assertion_failed"
    assert "expected='valid_workflow' actual='wf_v'" in run["final_blocker_note"]


# Layer: contract
def test_main_writes_diff_ledger_report(monkeypatch, tmp_path: Path) -> None:
    out_path = tmp_path / "benchmarks" / "staging" / "General" / "local_model_coding_challenge_report.json"

    def _fake_execute_challenge_run(**kwargs):
        workspace = Path(kwargs["workspace"])
        run_ordinal = 1 if workspace.name.endswith("01") else 2
        run_id = f"run-{run_ordinal:03d}"
        _write_json(
            workspace / "runs" / run_id / "run_summary.json",
            {
                "run_id": run_id,
                "status": "terminal_failure",
                "duration_ms": 1234,
                "failure_reason": "terminal_failure",
                "tools_used": [],
                "artifact_ids": [],
                "stop_reason": "terminal_failure",
                "cards_runtime": {
                    "repair_ledger": {
                        "entries": [
                            {
                                "issue_id": "CWR-04",
                                "turn_index": 7,
                                "reasons": ["artifact_semantic_contract_not_met"],
                            }
                        ],
                        "final_disposition": "accepted_with_repair",
                        "repair_count": 1,
                    },
                },
            },
        )
        _write_json(
            workspace / "observability" / run_id / "cwr-04" / "007_coder" / "parsed_tool_calls.json",
            [
                {
                    "tool": "write_file",
                    "args": {
                        "path": "agent_output/challenge_runtime/loader.py",
                        "content": "def load_workflow(path): return {}",
                    },
                }
            ],
        )
        _write_json(
            workspace / "observability" / run_id / "cwr-04" / "007_coder" / "messages.json",
            [{"role": "user", "content": "Retry Note: runtime stdout assertion failed: path=workflow_id"}],
        )
        (workspace / "agent_output" / "challenge_runtime").mkdir(parents=True, exist_ok=True)
        (workspace / "agent_output" / "challenge_runtime" / "loader.py").write_text(
            "def load_workflow(path):\n    return {}\n",
            encoding="utf-8",
        )
        return {"command": ["python", "main.py"], "exit_code": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(script, "_execute_challenge_run", _fake_execute_challenge_run)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path.relative_to(tmp_path)),
            "--workspace-root",
            ".tmp/local_model_coding_challenge",
            "--runs",
            "2",
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "complete"
    assert payload["observed_result"] == "partial success"
    assert payload["scoreboard"]["total_runs"] == 2
    assert payload["scoreboard"]["code_write_runs"] == 2
    assert payload["scoreboard"]["all_program_hashes_identical"] is True
    assert payload["runs"][0]["final_disposition"] == "accepted_with_repair"
    assert payload["runs"][0]["repair_count"] == 1
    assert "diff_ledger" in payload


def test_run_local_model_coding_challenge_records_prompt_patch_metadata(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies bounded challenge runs record the prompt patch label/checksum when a patch file is used."""
    patch_path = tmp_path / "prompt_patch.txt"
    patch_path.write_text("Prompt patch.\n", encoding="utf-8")

    def _fake_execute_challenge_run(**kwargs):
        workspace = Path(kwargs["workspace"])
        _write_json(
            workspace / "runs" / "run-001" / "run_summary.json",
            {
                "run_id": "run-001",
                "status": "failed",
                "stop_reason": "failed",
                "cards_runtime": {},
            },
        )
        return {"command": ["python", "main.py"], "exit_code": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(script, "_execute_challenge_run", _fake_execute_challenge_run)

    payload = script.run_local_model_coding_challenge(
        argparse.Namespace(
            repo_root=str(tmp_path),
            out="report.json",
            epic="challenge_workflow_runtime",
            provider="lmstudio",
            model="gemma-3-4b-it-qat",
            runs=1,
            workspace_root=".tmp/local_model_coding_challenge",
            build_id_prefix="local_model_coding_challenge",
            python_bin="python",
            prompt_patch_file=str(patch_path.relative_to(tmp_path)),
            prompt_patch_label="candidate-1",
        )
    )

    assert payload["prompt_patch"]["applied"] is True
    assert payload["prompt_patch"]["label"] == "candidate-1"
    assert payload["prompt_patch"]["source_ref"] == "prompt_patch.txt"


def test_summarize_run_flags_degraded_summary_as_non_primary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _write_json(
        workspace / "runs" / "run-001" / "run_summary.json",
        {
            "run_id": "run-001",
            "status": "failed",
            "duration_ms": 1234,
            "failure_reason": "summary_generation_failed",
            "tools_used": [],
            "artifact_ids": [],
            "stop_reason": "summary_generation_failed",
            "is_degraded": True,
        },
    )

    run = script._summarize_run(
        repo_root=tmp_path,
        workspace=workspace,
        epic="challenge_workflow_runtime",
        provider="lmstudio",
        model="google/gemma-4-26b-a4b",
        run_ordinal=1,
        execution={"command": ["python", "main.py"], "exit_code": 1, "stdout": "", "stderr": ""},
    )

    assert run["observed_path"] == "degraded"
    assert run["result"] == "failure"
    assert run["run_summary_warning"] == "run_summary_degraded"
