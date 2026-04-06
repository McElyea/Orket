# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.prompt_lab import run_prompt_reforger_gemma_tool_use_cycle as script


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_main_selects_best_candidate_and_pauses_on_partial_portability(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the cycle ranks bounded candidates by measured slice outcomes and records a pause decision."""
    out_path = tmp_path / "cycle.json"
    corpus_path = tmp_path / "corpus.json"
    _write_json(corpus_path, {"corpus_id": "challenge_workflow_runtime_bootstrap_v1"})

    inventory = {
        "inventory_targets": [
            {
                "role": "proposer_portability",
                "requested_provider": "lmstudio",
                "requested_model": "google/gemma-3-4b-it-qat",
                "runtime_target": {"status": "OK", "requested_model": "gemma-3-4b-it-qat"},
            },
            {
                "role": "proposer_quality",
                "requested_provider": "lmstudio",
                "requested_model": "google/gemma-3-12b-it-qat",
                "runtime_target": {"status": "OK", "requested_model": "gemma-3-12b-it-qat"},
            },
        ]
    }

    def _fake_candidate_run(**kwargs):
        target_role = str(kwargs["target_row"]["role"])
        candidate_id = str(kwargs["candidate"]["candidate_id"])
        accepted = 2
        if target_role == "proposer_portability" and candidate_id == "multi_write_completion_v1":
            accepted = 3
        if target_role == "proposer_quality" and candidate_id == "workflow_fixture_shape_v1":
            accepted = 4
        return {
            "candidate_id": candidate_id,
            "candidate_label": candidate_id,
            "selection_kind": "candidate" if candidate_id != "baseline" else "baseline",
            "prompt_patch": "",
            "prompt_patch_checksum": "",
            "challenge_report_ref": f"{target_role}/{candidate_id}/challenge_report.json",
            "score_report_ref": f"{target_role}/{candidate_id}/score_report.json",
            "judge_report_ref": f"{target_role}/{candidate_id}/judge_report.json",
            "challenge_observed_result": "partial success",
            "scoreboard": {
                "slices_total": 5,
                "accepted_slices": accepted,
                "partial_slices": 0,
                "rejected_slices": 5 - accepted,
                "not_exercised_slices": 0,
            },
            "judge_summary": {"turns_total": accepted},
            "judge_observed_path": "fallback",
            "judge_observed_result": "success",
            "blocking_error": "",
        }

    monkeypatch.setattr(script, "_ensure_inventory", lambda repo_root, inventory_path: inventory)
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
            "both",
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    portability = next(row for row in payload["target_results"] if row["target_role"] == "proposer_portability")
    quality = next(row for row in payload["target_results"] if row["target_role"] == "proposer_quality")
    assert exit_code == 0
    assert portability["winning_candidate_id"] == "multi_write_completion_v1"
    assert quality["winning_candidate_id"] == "workflow_fixture_shape_v1"
    assert payload["promotion_decision"]["decision"] == "pause_lane_with_blockers"
    assert "diff_ledger" in payload


def test_run_cycle_keeps_all_gemma_primary_when_portability_and_quality_clear(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the cycle records keep_all_gemma_primary only when the frozen portability corpus clears."""
    corpus_path = tmp_path / "corpus.json"
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

    def _fake_candidate_run(**kwargs):
        return {
            "candidate_id": "baseline",
            "candidate_label": "baseline",
            "selection_kind": "baseline",
            "prompt_patch": "",
            "prompt_patch_checksum": "",
            "challenge_report_ref": "challenge_report.json",
            "score_report_ref": "score_report.json",
            "judge_report_ref": "judge_report.json",
            "challenge_observed_result": "success",
            "scoreboard": {
                "slices_total": 5,
                "accepted_slices": 5,
                "partial_slices": 0,
                "rejected_slices": 0,
                "not_exercised_slices": 0,
            },
            "judge_summary": {"turns_total": 5},
            "judge_observed_path": "fallback",
            "judge_observed_result": "success",
            "blocking_error": "",
        }

    monkeypatch.setattr(script, "_ensure_inventory", lambda repo_root, inventory_path: inventory)
    monkeypatch.setattr(script, "_candidate_run", _fake_candidate_run)

    payload = script.run_cycle(
        script.argparse.Namespace(
            repo_root=str(tmp_path),
            inventory="inventory.json",
            corpus=str(corpus_path.relative_to(tmp_path)),
            out="cycle.json",
            work_root=".tmp/work",
            runs=1,
            targets="portability",
            judge_timeout_sec=30,
        )
    )

    assert payload["promotion_decision"]["decision"] == "keep_all_gemma_primary"
    assert payload["observed_result"] == "success"
