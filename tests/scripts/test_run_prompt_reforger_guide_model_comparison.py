from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.prompt_lab import guide_model_prompt_patch as guide_script
from scripts.prompt_lab import run_prompt_reforger_guide_model_comparison as script


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_generate_guide_candidate_emits_bounded_prompt_patch(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the guide-model generator captures one bounded prompt-patch candidate through the native-tool path."""

    class _FakeProvider:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        async def complete(self, messages, runtime_context):  # noqa: ANN001
            del messages, runtime_context
            return SimpleNamespace(
                content="",
                raw={
                    "tool_calls": [
                        {
                            "function": {
                                "name": "emit_prompt_patch",
                                "arguments": json.dumps(
                                    {
                                        "candidate_label": "Qwen guide",
                                        "prompt_patch": "Add one write_file call for every required write path before update_issue_status.",
                                        "improvement_hypothesis": "Helps the multi-write coder slice clear all required writes.",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        guide_script,
        "warmup_provider_model",
        lambda **kwargs: {
            "requested_provider": kwargs["provider"],
            "requested_model": kwargs["requested_model"],
            "resolved_model": kwargs["requested_model"],
            "base_url": "",
            "status": "OK",
            "resolution_mode": "canonical",
        },
    )
    monkeypatch.setattr(guide_script, "LocalModelProvider", _FakeProvider)

    out_path = tmp_path / "guide_generation.json"
    payload = guide_script.generate_guide_candidate(
        repo_root=tmp_path,
        corpus={
            "corpus_id": "challenge_workflow_runtime_bootstrap_v1",
            "tool_call_contract_family": "challenge_workflow_runtime.turn_contract.v1",
            "measured_outputs": ["accepted_tool_calls"],
            "slices": [
                {
                    "slice_id": "SLICE-01",
                    "issue_id": "CWR-01",
                    "role_name": "coder",
                    "description": "Single write.",
                    "required_action_tools": ["write_file", "update_issue_status"],
                    "required_read_paths": [],
                    "required_write_paths": ["agent_output/requirements.txt"],
                    "required_statuses": ["code_review"],
                }
            ],
        },
        corpus_ref="docs/projects/PromptReforgerToolCompatibility/GEMMA_TOOL_USE_CHALLENGE_CORPUS_V1.json",
        target_role="proposer_portability",
        target_model="gemma-3-4b-it-qat",
        guide_spec=guide_script.GuideModelSpec(label="qwen7b", provider="ollama", model="qwen2.5-coder:7b"),
        out_path=out_path,
        timeout_sec=30,
    )

    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["observed_path"] == "primary"
    assert payload["observed_result"] == "success"
    assert payload["generated_candidate"]["selection_kind"] == "guide_model"
    assert payload["generated_candidate"]["candidate_id"] == "guide_qwen7b"
    assert "diff_ledger" in written


def test_main_ranks_guides_by_candidate_generation_quality(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies guide comparison ranks models by score deltas over baseline rather than outer challenge status."""
    corpus_path = tmp_path / "corpus.json"
    out_path = tmp_path / "comparison.json"
    _write_json(corpus_path, {"corpus_id": "challenge_workflow_runtime_bootstrap_v1"})

    inventory = {
        "inventory_targets": [
            {
                "role": "proposer_portability",
                "requested_provider": "lmstudio",
                "requested_model": "google/gemma-3-4b-it-qat",
                "runtime_target": {"status": "OK", "requested_model": "gemma-3-4b-it-qat"},
            }
        ]
    }

    def _fake_generate_guide_candidate(**kwargs):
        guide_label = kwargs["guide_spec"].label
        return {
            "observed_path": "primary",
            "observed_result": "success",
            "blocking_error": "",
            "generated_candidate": {
                "candidate_id": f"guide_{guide_label}",
                "label": f"Guide {guide_label}",
                "selection_kind": "guide_model",
                "prompt_patch": f"Patch for {guide_label}",
                "prompt_patch_checksum": f"chk-{guide_label}",
            },
        }

    def _fake_candidate_run(**kwargs):
        candidate_id = str(kwargs["candidate"]["candidate_id"])
        accepted = 2
        if candidate_id == "guide_qwen7b":
            accepted = 4
        if candidate_id == "guide_gemma12b":
            accepted = 3
        return {
            "candidate_id": candidate_id,
            "candidate_label": candidate_id,
            "selection_kind": "baseline" if candidate_id == "baseline" else "guide_model",
            "prompt_patch": "",
            "prompt_patch_checksum": "",
            "challenge_report_ref": f"{candidate_id}/challenge_report.json",
            "score_report_ref": f"{candidate_id}/score_report.json",
            "challenge_observed_result": "partial success",
            "scoreboard": {
                "slices_total": 5,
                "accepted_slices": accepted,
                "partial_slices": 0,
                "rejected_slices": 5 - accepted,
                "not_exercised_slices": 0,
            },
            "blocking_error": "",
        }

    monkeypatch.setattr(script.cycle_script, "_ensure_inventory", lambda repo_root, inventory_path: inventory)
    monkeypatch.setattr(script.guide_script, "generate_guide_candidate", _fake_generate_guide_candidate)
    monkeypatch.setattr(script, "_candidate_run", _fake_candidate_run)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--corpus",
            str(corpus_path.relative_to(tmp_path)),
            "--out",
            str(out_path.relative_to(tmp_path)),
            "--targets",
            "portability",
            "--guide-spec",
            "qwen7b|ollama|qwen2.5-coder:7b",
            "--guide-spec",
            "gemma12b|lmstudio|google/gemma-3-12b-it-qat",
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    target = payload["target_results"][0]
    qwen = next(row for row in target["guide_results"] if row["guide_label"] == "qwen7b")
    gemma = next(row for row in target["guide_results"] if row["guide_label"] == "gemma12b")

    assert exit_code == 0
    assert target["winning_guide_label"] == "qwen7b"
    assert qwen["candidate_generation_quality"]["accepted_delta_vs_baseline"] == 2
    assert qwen["candidate_generation_quality"]["improves_over_baseline"] is True
    assert gemma["candidate_generation_quality"]["accepted_delta_vs_baseline"] == 1
    assert payload["summary"]["improved_guide_runs"] == 2
    assert "diff_ledger" in payload
