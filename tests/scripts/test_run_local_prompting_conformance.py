from __future__ import annotations

import json
from pathlib import Path

import scripts.protocol.run_local_prompting_conformance as conformance_script
from scripts.protocol.run_local_prompting_conformance import main


def test_run_local_prompting_conformance_writes_required_artifacts(tmp_path: Path) -> None:
    out_root = tmp_path / "local_prompting"
    exit_code = main(
        [
            "--provider",
            "openai_compat",
            "--model",
            "qwen3.5-4b",
            "--cases",
            "3",
            "--mock",
            "--strict",
            "--out-root",
            str(out_root),
        ]
    )
    assert exit_code == 0

    profile_root = out_root / "conformance" / "openai_compat" / "openai_compat.qwen.openai_messages.v1"
    assert (profile_root / "strict_json_report.json").exists()
    assert (profile_root / "tool_call_report.json").exists()
    assert (profile_root / "anti_meta_report.json").exists()
    assert (profile_root / "sampling_capabilities.json").exists()
    assert (profile_root / "render_verification.json").exists()
    assert (profile_root / "capability_probe_method.json").exists()
    assert (profile_root / "suite_manifest.json").exists()
    assert (profile_root / "tokenizer_identity.json").exists()

    strict_report = json.loads((profile_root / "strict_json_report.json").read_text(encoding="utf-8"))
    assert strict_report["strict_ok"] is True
    assert strict_report["task_class"] == "strict_json"
    assert "anti_meta_counts" in strict_report

    anti_meta_report = json.loads((profile_root / "anti_meta_report.json").read_text(encoding="utf-8"))
    assert anti_meta_report["strict_ok"] is True
    assert anti_meta_report["protocol_chatter_rate"] == 0.0

    suite_manifest = json.loads((profile_root / "suite_manifest.json").read_text(encoding="utf-8"))
    assert suite_manifest["suite"] == "smoke"
    assert len(suite_manifest["strict_json_case_ids"]) == 3
    assert len(suite_manifest["tool_call_case_ids"]) == 3
    assert suite_manifest["lmstudio_session_mode"] == "none"
    assert suite_manifest["lmstudio_session_id_present"] is False

    profiles_root = out_root / "profiles"
    assert (profiles_root / "profile_registry_snapshot.json").exists()
    assert (profiles_root / "profile_registry_snapshot.sha256").exists()
    assert (profiles_root / "enabled_pack.json").exists()
    assert (profiles_root / "error_code_registry_snapshot.json").exists()


def test_run_local_prompting_conformance_records_lmstudio_session_mode_in_manifest(tmp_path: Path) -> None:
    out_root = tmp_path / "local_prompting"
    exit_code = main(
        [
            "--provider",
            "openai_compat",
            "--model",
            "qwen3.5-4b",
            "--cases",
            "1",
            "--mock",
            "--strict",
            "--lmstudio-session-mode",
            "fixed",
            "--lmstudio-session-id",
            "session-fixed-01",
            "--out-root",
            str(out_root),
        ]
    )
    assert exit_code == 0

    profile_root = out_root / "conformance" / "openai_compat" / "openai_compat.qwen.openai_messages.v1"
    suite_manifest = json.loads((profile_root / "suite_manifest.json").read_text(encoding="utf-8"))
    assert suite_manifest["lmstudio_session_mode"] == "fixed"
    assert suite_manifest["lmstudio_session_id_present"] is True


def test_run_local_prompting_conformance_sanitizes_lmstudio_cache_pre_and_post(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "local_prompting"
    stages: list[str] = []

    def _fake_clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool):  # noqa: ANN001
        stages.append(stage)
        return {"stage": stage, "status": "OK", "base_url": base_url, "timeout_sec": timeout_sec, "strict": strict}

    monkeypatch.setattr(conformance_script, "clear_loaded_models", _fake_clear_loaded_models)
    exit_code = main(
        [
            "--provider",
            "lmstudio",
            "--model",
            "qwen3.5-4b",
            "--cases",
            "1",
            "--mock",
            "--strict",
            "--out-root",
            str(out_root),
        ]
    )
    assert exit_code == 0
    assert stages == ["pre_run", "post_run"]
    profile_root = out_root / "conformance" / "openai_compat" / "openai_compat.qwen.openai_messages.v1"
    suite_manifest = json.loads((profile_root / "suite_manifest.json").read_text(encoding="utf-8"))
    sanitation = suite_manifest["model_cache_sanitation"]
    assert sanitation["enabled"] is True
    assert [entry["stage"] for entry in sanitation["events"]] == ["pre_run", "post_run"]


def test_run_local_prompting_conformance_can_disable_lmstudio_cache_sanitation(tmp_path: Path, monkeypatch) -> None:
    out_root = tmp_path / "local_prompting"
    calls = {"count": 0}

    def _fake_clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool):  # noqa: ANN001
        calls["count"] += 1
        return {"stage": stage, "status": "OK"}

    monkeypatch.setattr(conformance_script, "clear_loaded_models", _fake_clear_loaded_models)
    exit_code = main(
        [
            "--provider",
            "lmstudio",
            "--model",
            "qwen3.5-4b",
            "--cases",
            "1",
            "--mock",
            "--strict",
            "--no-sanitize-model-cache",
            "--out-root",
            str(out_root),
        ]
    )
    assert exit_code == 0
    assert calls["count"] == 0
    profile_root = out_root / "conformance" / "openai_compat" / "openai_compat.qwen.openai_messages.v1"
    suite_manifest = json.loads((profile_root / "suite_manifest.json").read_text(encoding="utf-8"))
    sanitation = suite_manifest["model_cache_sanitation"]
    assert sanitation["enabled"] is False
    assert [entry["status"] for entry in sanitation["events"]] == ["NOT_APPLICABLE", "NOT_APPLICABLE"]
