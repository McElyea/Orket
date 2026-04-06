# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.prompt_lab import score_prompt_reforger_gemma_tool_use_corpus as script


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_main_scores_bootstrap_corpus_from_observed_turns(tmp_path: Path) -> None:
    """Layer: contract. Verifies the bounded Gemma tool-use scorer emits the fixed measured outputs from run artifacts."""
    repo_root = tmp_path
    run_summary_path = repo_root / "runs" / "run-001" / "run_summary.json"
    observability_root = repo_root / "observability" / "run-001"
    out_path = repo_root / "benchmarks" / "staging" / "General" / "prompt_reforger_gemma_tool_use_score.json"
    corpus_path = Path("c:/Source/Orket/docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json")

    _write_json(
        run_summary_path,
        {
            "run_id": "run-001",
            "status": "terminal_failure",
            "stop_reason": "terminal_failure",
            "truthful_runtime_packet2": {
                "repair_ledger": {
                    "entries": [{"issue_id": "CWR-04", "turn_index": 7}],
                }
            },
        },
    )
    _write_json(
        observability_root / "cwr-01" / "001_coder" / "parsed_tool_calls.json",
        [
            {"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "ok"}},
            {"tool": "update_issue_status", "args": {"status": "code_review"}},
        ],
    )
    _write_json(observability_root / "cwr-01" / "001_coder" / "tool_parser_diagnostics.json", [])
    _write_json(
        observability_root / "cwr-01" / "002_integrity_guard" / "parsed_tool_calls.json",
        [
            {"tool": "read_file", "args": {"path": "agent_output/requirements.txt"}},
            {"tool": "update_issue_status", "args": {"status": "done"}},
        ],
    )
    _write_json(observability_root / "cwr-01" / "002_integrity_guard" / "tool_parser_diagnostics.json", [])
    _write_json(
        observability_root / "cwr-03" / "005_coder" / "parsed_tool_calls.json",
        [
            {"tool": "write_file", "args": {"path": "agent_output/challenge_inputs/workflow_valid.json", "content": "a"}},
            {"tool": "write_file", "args": {"path": "agent_output/challenge_inputs/workflow_cycle.json", "content": "b"}},
            {"tool": "write_file", "args": {"path": "agent_output/challenge_inputs/workflow_retry.json", "content": "c"}},
            {"tool": "update_issue_status", "args": {"status": "code_review"}},
        ],
    )
    _write_json(observability_root / "cwr-03" / "005_coder" / "tool_parser_diagnostics.json", [])
    _write_json(
        observability_root / "cwr-03" / "006_integrity_guard" / "parsed_tool_calls.json",
        [
            {"tool": "read_file", "args": {"path": "agent_output/challenge_inputs/workflow_valid.json"}},
            {"tool": "read_file", "args": {"path": "agent_output/challenge_inputs/workflow_cycle.json"}},
            {"tool": "read_file", "args": {"path": "agent_output/challenge_inputs/workflow_retry.json"}},
            {"tool": "update_issue_status", "args": {"status": "done"}},
        ],
    )
    _write_json(observability_root / "cwr-03" / "006_integrity_guard" / "tool_parser_diagnostics.json", [])
    _write_json(
        observability_root / "cwr-04" / "007_coder" / "parsed_tool_calls.json",
        [
            {"tool": "write_file", "args": {"path": "agent_output/challenge_runtime/__init__.py", "content": "a"}},
            {"tool": "write_file", "args": {"path": "agent_output/challenge_runtime/models.py", "content": "b"}},
            {"tool": "write_file", "args": {"path": "agent_output/challenge_runtime/loader.py", "content": "c"}},
            {"tool": "update_issue_status", "args": {"status": "code_review"}},
        ],
    )
    _write_json(
        observability_root / "cwr-04" / "007_coder" / "tool_parser_diagnostics.json",
        [{"stage": "native_tool_call_skipped", "data": {"tool": "add_issue_comment", "reason": "undeclared_tool"}}],
    )

    exit_code = script.main(
        [
            "--repo-root",
            str(repo_root),
            "--run-summary",
            str(run_summary_path.relative_to(repo_root)),
            "--observability-root",
            str(observability_root.relative_to(repo_root)),
            "--corpus",
            str(corpus_path),
            "--out",
            str(out_path.relative_to(repo_root)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["observed_path"] == "primary"
    assert payload["observed_result"] == "success"
    assert payload["scoreboard"]["accepted_slices"] == 5
    assert payload["slice_results"][0]["turns_to_first_valid_completion"] == 1
    assert payload["slice_results"][4]["final_disposition"] == "accepted_with_repair"
    assert payload["slice_results"][4]["evaluated_turns"][0]["rejected_tool_calls"][0]["reason"] == "undeclared_tool"
    assert "diff_ledger" in payload
