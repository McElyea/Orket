# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.prompt_lab import run_functiongemma_tool_call_judge as script


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_main_blocks_when_no_judge_path_is_available(tmp_path: Path) -> None:
    """Layer: contract. Verifies the advisory judge reports an environment blocker when inventory has no admitted judge path."""
    score_report_path = tmp_path / "score.json"
    inventory_path = tmp_path / "inventory.json"
    out_path = tmp_path / "judge.json"
    _write_json(score_report_path, {"slice_results": []})
    _write_json(inventory_path, {"summary": {"judge_path": "blocked"}, "inventory_targets": []})

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--score-report",
            str(score_report_path.relative_to(tmp_path)),
            "--inventory",
            str(inventory_path.relative_to(tmp_path)),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["observed_path"] == "blocked"
    assert payload["observed_result"] == "environment blocker"
    assert payload["blocking_error"] == "inventory_judge_path_blocked"
    assert "diff_ledger" in payload


def test_main_records_fallback_judge_verdicts(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the advisory judge records fallback FunctionGemma verdicts without overriding parser truth."""
    score_report_path = tmp_path / "score.json"
    inventory_path = tmp_path / "inventory.json"
    out_path = tmp_path / "judge.json"
    _write_json(tmp_path / "obs" / "messages.json", [{"role": "system", "content": "SYSTEM"}])
    _write_json(tmp_path / "obs" / "model_response_raw.json", {"tool_calls": [{"function": {"name": "write_file"}}]})
    _write_json(
        tmp_path / "obs" / "parsed_tool_calls.json",
        [{"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}],
    )
    _write_json(tmp_path / "obs" / "tool_parser_diagnostics.json", [{"stage": "native_tool_calls_success", "data": {}}])
    _write_json(
        score_report_path,
        {
            "slice_results": [
                {
                    "slice_id": "PRGTU-CWR01-CODER-SINGLE-WRITE",
                    "issue_id": "CWR-01",
                    "role_name": "coder",
                    "description": "desc",
                    "required_action_tools": ["write_file", "update_issue_status"],
                    "required_read_paths": [],
                    "required_write_paths": ["agent_output/requirements.txt"],
                    "required_statuses": ["code_review"],
                    "evaluated_turns": [
                        {
                            "turn_dir": "001_coder",
                            "turn_index": 1,
                            "accepted_tool_calls": [
                                {"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}
                            ],
                            "rejected_tool_calls": [],
                            "argument_shape_defects": [],
                            "valid_completion": False,
                            "messages_ref": "obs/messages.json",
                            "model_response_raw_ref": "obs/model_response_raw.json",
                            "parsed_tool_calls_ref": "obs/parsed_tool_calls.json",
                            "tool_parser_diagnostics_ref": "obs/tool_parser_diagnostics.json",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        inventory_path,
        {
            "summary": {"judge_path": "fallback"},
            "inventory_targets": [
                {
                    "role": "judge_fallback",
                    "requested_provider": "lmstudio",
                    "requested_model": "google/functiongemma-270m",
                    "preferred_quantization": "Q8_0",
                    "alias_resolution": "explicit_alias_candidate",
                    "model_identity": "google/functiongemma-270m",
                    "runtime_target": {
                        "status": "OK",
                        "requested_model": "functiongemma-270m-it",
                        "base_url": "http://127.0.0.1:1234/v1",
                    },
                }
            ],
        },
    )

    class _FakeProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def complete(self, messages, runtime_context=None):
            return SimpleNamespace(
                content=json.dumps(
                    {
                        "verdict": "fail",
                        "dimensions": {
                            "tool_selection": "fail",
                            "argument_presence": "pass",
                            "argument_shape": "pass",
                            "extra_undeclared_tool_calls": "pass",
                            "malformed_output_shape": "pass",
                        },
                        "rationale": "Missing required status update.",
                    }
                ),
                raw={"provider": "fake"},
            )

        async def close(self):
            return None

    monkeypatch.setattr(script, "LocalModelProvider", _FakeProvider)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--score-report",
            str(score_report_path.relative_to(tmp_path)),
            "--inventory",
            str(inventory_path.relative_to(tmp_path)),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["observed_path"] == "fallback"
    assert payload["judge_target"]["model"] == "functiongemma-270m-it"
    assert payload["summary"]["turns_total"] == 1
    assert payload["summary"]["agreement_count"] == 1
    assert payload["turn_judgments"][0]["judge_advisory_verdict"]["verdict"] == "fail"
    assert payload["turn_judgments"][0]["parser_authority_truth"]["verdict"] == "fail"


def test_main_prefers_native_tool_call_payload_and_normalizes_flat_dimensions(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the judge prefers native tool-call arguments over prose and normalizes the flat tool schema."""
    score_report_path = tmp_path / "score.json"
    inventory_path = tmp_path / "inventory.json"
    out_path = tmp_path / "judge.json"
    _write_json(tmp_path / "obs" / "messages.json", [{"role": "system", "content": "SYSTEM"}])
    _write_json(tmp_path / "obs" / "model_response_raw.json", {"tool_calls": [{"function": {"name": "write_file"}}]})
    _write_json(
        tmp_path / "obs" / "parsed_tool_calls.json",
        [{"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}],
    )
    _write_json(tmp_path / "obs" / "tool_parser_diagnostics.json", [{"stage": "native_tool_calls_success", "data": {}}])
    _write_json(
        score_report_path,
        {
            "slice_results": [
                {
                    "slice_id": "PRGTU-CWR01-CODER-SINGLE-WRITE",
                    "issue_id": "CWR-01",
                    "role_name": "coder",
                    "description": "desc",
                    "required_action_tools": ["write_file", "update_issue_status"],
                    "required_read_paths": [],
                    "required_write_paths": ["agent_output/requirements.txt"],
                    "required_statuses": ["code_review"],
                    "evaluated_turns": [
                        {
                            "turn_dir": "001_coder",
                            "turn_index": 1,
                            "accepted_tool_calls": [
                                {"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}
                            ],
                            "rejected_tool_calls": [],
                            "argument_shape_defects": [],
                            "valid_completion": False,
                            "messages_ref": "obs/messages.json",
                            "model_response_raw_ref": "obs/model_response_raw.json",
                            "parsed_tool_calls_ref": "obs/parsed_tool_calls.json",
                            "tool_parser_diagnostics_ref": "obs/tool_parser_diagnostics.json",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        inventory_path,
        {
            "summary": {"judge_path": "fallback"},
            "inventory_targets": [
                {
                    "role": "judge_fallback",
                    "requested_provider": "lmstudio",
                    "requested_model": "google/functiongemma-270m",
                    "preferred_quantization": "Q8_0",
                    "alias_resolution": "explicit_alias_candidate",
                    "model_identity": "google/functiongemma-270m",
                    "runtime_target": {
                        "status": "OK",
                        "requested_model": "functiongemma-270m-it",
                        "base_url": "http://127.0.0.1:1234/v1",
                    },
                }
            ],
        },
    )

    class _FakeProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def complete(self, messages, runtime_context=None):
            _ = (messages, runtime_context)
            return SimpleNamespace(
                content='{"verdict":"pass"}',
                raw={
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "emit_judgment",
                                "arguments": json.dumps(
                                    {
                                        "verdict": "fail",
                                        "tool_selection": "fail",
                                        "argument_presence": "pass",
                                        "argument_shape": "pass",
                                        "extra_undeclared_tool_calls": [],
                                        "malformed_output_shape": "pass",
                                        "Rationale": "missing required update_issue_status",
                                    }
                                ),
                            },
                        }
                    ]
                },
            )

        async def close(self):
            return None

    monkeypatch.setattr(script, "LocalModelProvider", _FakeProvider)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--score-report",
            str(score_report_path.relative_to(tmp_path)),
            "--inventory",
            str(inventory_path.relative_to(tmp_path)),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    verdict = payload["turn_judgments"][0]["judge_advisory_verdict"]
    assert exit_code == 0
    assert verdict["verdict"] == "fail"
    assert verdict["dimensions"]["tool_selection"] == "fail"
    assert verdict["dimensions"]["extra_undeclared_tool_calls"] == "pass"
    assert verdict["rationale"] == "missing required update_issue_status"
    assert payload["turn_judgments"][0]["judge_response"]["raw"]["judge_tool_call_count"] == 1


def test_main_falls_back_when_primary_judge_path_is_all_inconclusive(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the judge can step down from an all-inconclusive primary path to the admitted fallback path."""
    score_report_path = tmp_path / "score.json"
    inventory_path = tmp_path / "inventory.json"
    out_path = tmp_path / "judge.json"
    _write_json(tmp_path / "obs" / "messages.json", [{"role": "system", "content": "SYSTEM"}])
    _write_json(tmp_path / "obs" / "model_response_raw.json", {"tool_calls": [{"function": {"name": "write_file"}}]})
    _write_json(
        tmp_path / "obs" / "parsed_tool_calls.json",
        [{"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}],
    )
    _write_json(tmp_path / "obs" / "tool_parser_diagnostics.json", [{"stage": "native_tool_calls_success", "data": {}}])
    _write_json(
        score_report_path,
        {
            "slice_results": [
                {
                    "slice_id": "PRGTU-CWR01-CODER-SINGLE-WRITE",
                    "issue_id": "CWR-01",
                    "role_name": "coder",
                    "description": "desc",
                    "required_action_tools": ["write_file", "update_issue_status"],
                    "required_read_paths": [],
                    "required_write_paths": ["agent_output/requirements.txt"],
                    "required_statuses": ["code_review"],
                    "evaluated_turns": [
                        {
                            "turn_dir": "001_coder",
                            "turn_index": 1,
                            "accepted_tool_calls": [
                                {"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "x"}}
                            ],
                            "rejected_tool_calls": [],
                            "argument_shape_defects": [],
                            "valid_completion": False,
                            "messages_ref": "obs/messages.json",
                            "model_response_raw_ref": "obs/model_response_raw.json",
                            "parsed_tool_calls_ref": "obs/parsed_tool_calls.json",
                            "tool_parser_diagnostics_ref": "obs/tool_parser_diagnostics.json",
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        inventory_path,
        {
            "summary": {"judge_path": "primary"},
            "inventory_targets": [
                {
                    "role": "judge_primary",
                    "requested_provider": "ollama",
                    "requested_model": "functiongemma",
                    "preferred_quantization": "Q8_0",
                    "alias_resolution": "explicit_alias_candidate",
                    "model_identity": "google/functiongemma-270m-it",
                    "runtime_target": {
                        "status": "OK",
                        "requested_model": "functiongemma:latest",
                        "base_url": "http://127.0.0.1:11434",
                    },
                },
                {
                    "role": "judge_fallback",
                    "requested_provider": "lmstudio",
                    "requested_model": "google/functiongemma-270m",
                    "preferred_quantization": "Q8_0",
                    "alias_resolution": "explicit_alias_candidate",
                    "model_identity": "google/functiongemma-270m",
                    "runtime_target": {
                        "status": "OK",
                        "requested_model": "functiongemma-270m-it",
                        "base_url": "http://127.0.0.1:1234/v1",
                    },
                },
            ],
        },
    )

    class _FakeProvider:
        def __init__(self, **kwargs):
            self.provider = kwargs["provider"]

        async def complete(self, messages, runtime_context=None):
            _ = (messages, runtime_context)
            if self.provider == "ollama":
                return SimpleNamespace(content="", raw={"tool_calls": []})
            return SimpleNamespace(
                content="",
                raw={
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "emit_judgment",
                                "arguments": json.dumps(
                                    {
                                        "verdict": "fail",
                                        "tool_selection": "fail",
                                        "argument_presence": "pass",
                                        "argument_shape": "pass",
                                        "extra_undeclared_tool_calls": "pass",
                                        "malformed_output_shape": "pass",
                                        "rationale": "missing required update_issue_status",
                                    }
                                ),
                            },
                        }
                    ]
                },
            )

        async def close(self):
            return None

    monkeypatch.setattr(script, "LocalModelProvider", _FakeProvider)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--score-report",
            str(score_report_path.relative_to(tmp_path)),
            "--inventory",
            str(inventory_path.relative_to(tmp_path)),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["observed_path"] == "fallback"
    assert payload["judge_target"]["provider"] == "lmstudio"
    assert [row["observed_path"] for row in payload["attempted_judge_targets"]] == ["primary", "fallback"]
    assert payload["turn_judgments"][0]["judge_advisory_verdict"]["verdict"] == "fail"
