# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.prompt_lab import run_prompt_reforger_gemma_tool_use_inventory as script


def test_main_writes_diff_ledger_and_marks_degraded_when_12b_is_blocked(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the Gemma lane inventory writes the canonical artifact and degrades truthfully."""
    out_path = tmp_path / "benchmarks" / "staging" / "General" / "prompt_reforger_gemma_tool_use_inventory.json"
    responses = {
        ("lmstudio", "google/gemma-3-12b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/gemma-3-12b-it-qat",
            "model_id": "",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "unresolved",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("lmstudio", "gemma-3-12b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "gemma-3-12b-it-qat",
            "model_id": "",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "unresolved",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("lmstudio", "google/gemma-3-4b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/gemma-3-4b-it-qat",
            "model_id": "google/gemma-3-4b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": ["google/gemma-3-4b-it-qat"],
            "loaded_models_after": ["google/gemma-3-4b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("lmstudio", "gemma-3-4b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "gemma-3-4b-it-qat",
            "model_id": "gemma-3-4b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["gemma-3-4b-it-qat"],
            "loaded_models_before": ["gemma-3-4b-it-qat"],
            "loaded_models_after": ["gemma-3-4b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("ollama", "functiongemma"): {
            "requested_provider": "ollama",
            "canonical_provider": "ollama",
            "requested_model": "functiongemma",
            "model_id": "functiongemma",
            "base_url": "http://127.0.0.1:11434",
            "resolution_mode": "requested",
            "inventory_source": "ollama_list",
            "available_models": ["functiongemma"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("ollama", "functiongemma:latest"): {
            "requested_provider": "ollama",
            "canonical_provider": "ollama",
            "requested_model": "functiongemma:latest",
            "model_id": "functiongemma:latest",
            "base_url": "http://127.0.0.1:11434",
            "resolution_mode": "requested",
            "inventory_source": "ollama_list",
            "available_models": ["functiongemma:latest"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("lmstudio", "google/functiongemma-270m"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/functiongemma-270m",
            "model_id": "",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "unresolved",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("lmstudio", "functiongemma-270m-it"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "functiongemma-270m-it",
            "model_id": "",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "unresolved",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
    }

    def _fake_warmup_provider_model(**kwargs):
        return responses[(str(kwargs["provider"]), str(kwargs["requested_model"]))]

    monkeypatch.setattr(script, "warmup_provider_model", _fake_warmup_provider_model)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["lane_readiness"] == "degraded"
    assert payload["observed_path"] == "degraded"
    assert payload["observed_result"] == "partial success"
    assert payload["judge_quant_guidance"]["preferred_quantization"] == "Q8_0"
    assert payload["bootstrap_proof_slice"]["epic_ref"] == "model/core/epics/challenge_workflow_runtime.json"
    assert payload["canonical_output_paths"]["runtime_inventory"] == (
        "benchmarks/staging/General/prompt_reforger_gemma_tool_use_inventory.json"
    )
    quality_row = next(row for row in payload["inventory_targets"] if row["role"] == "proposer_quality")
    assert "google/gemma-3-12b-it-qat" in quality_row["blocking_error"]
    portability_row = next(row for row in payload["inventory_targets"] if row["role"] == "proposer_portability")
    assert portability_row["alias_resolution"] == "canonical"
    assert "diff_ledger" in payload


def test_main_uses_fallback_when_primary_judge_is_blocked(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies the lane records fallback when the primary judge is blocked but the LM Studio judge is present."""
    out_path = tmp_path / "prompt_reforger_gemma_tool_use_inventory.json"
    responses = {
        ("lmstudio", "google/gemma-3-12b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/gemma-3-12b-it-qat",
            "model_id": "google/gemma-3-12b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-12b-it-qat"],
            "loaded_models_before": ["google/gemma-3-12b-it-qat"],
            "loaded_models_after": ["google/gemma-3-12b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("lmstudio", "gemma-3-12b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "gemma-3-12b-it-qat",
            "model_id": "gemma-3-12b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["gemma-3-12b-it-qat"],
            "loaded_models_before": ["gemma-3-12b-it-qat"],
            "loaded_models_after": ["gemma-3-12b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("lmstudio", "google/gemma-3-4b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/gemma-3-4b-it-qat",
            "model_id": "google/gemma-3-4b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["google/gemma-3-4b-it-qat"],
            "loaded_models_before": ["google/gemma-3-4b-it-qat"],
            "loaded_models_after": ["google/gemma-3-4b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("lmstudio", "gemma-3-4b-it-qat"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "gemma-3-4b-it-qat",
            "model_id": "gemma-3-4b-it-qat",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["gemma-3-4b-it-qat"],
            "loaded_models_before": ["gemma-3-4b-it-qat"],
            "loaded_models_after": ["gemma-3-4b-it-qat"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
        ("ollama", "functiongemma"): {
            "requested_provider": "ollama",
            "canonical_provider": "ollama",
            "requested_model": "functiongemma",
            "model_id": "",
            "base_url": "http://127.0.0.1:11434",
            "resolution_mode": "unresolved",
            "inventory_source": "ollama_list",
            "available_models": [],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("ollama", "functiongemma:latest"): {
            "requested_provider": "ollama",
            "canonical_provider": "ollama",
            "requested_model": "functiongemma:latest",
            "model_id": "",
            "base_url": "http://127.0.0.1:11434",
            "resolution_mode": "unresolved",
            "inventory_source": "ollama_list",
            "available_models": [],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("lmstudio", "google/functiongemma-270m"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "google/functiongemma-270m",
            "model_id": "",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "unresolved",
            "inventory_source": "lms_cli",
            "available_models": ["functiongemma-270m-it"],
            "loaded_models_before": [],
            "loaded_models_after": [],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "BLOCKED",
        },
        ("lmstudio", "functiongemma-270m-it"): {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "functiongemma-270m-it",
            "model_id": "functiongemma-270m-it",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "requested_loaded",
            "inventory_source": "lms_cli",
            "available_models": ["functiongemma-270m-it"],
            "loaded_models_before": ["functiongemma-270m-it"],
            "loaded_models_after": ["functiongemma-270m-it"],
            "auto_load_attempted": False,
            "auto_load_performed": False,
            "status": "OK",
        },
    }

    def _fake_warmup_provider_model(**kwargs):
        return responses[(str(kwargs["provider"]), str(kwargs["requested_model"]))]

    monkeypatch.setattr(script, "warmup_provider_model", _fake_warmup_provider_model)

    exit_code = script.main(
        [
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_path.relative_to(tmp_path)),
        ]
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["lane_readiness"] == "degraded"
    assert payload["observed_path"] == "fallback"
    assert payload["summary"]["judge_path"] == "fallback"
    assert payload["summary"]["judge_fallback_available"] is True
    judge_row = next(row for row in payload["inventory_targets"] if row["role"] == "judge_fallback")
    assert judge_row["alias_resolution"] == "explicit_alias_candidate"
    assert judge_row["runtime_target"]["requested_model"] == "functiongemma-270m-it"
