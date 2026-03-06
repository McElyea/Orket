from __future__ import annotations

import json
from pathlib import Path

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

    profiles_root = out_root / "profiles"
    assert (profiles_root / "profile_registry_snapshot.json").exists()
    assert (profiles_root / "profile_registry_snapshot.sha256").exists()
    assert (profiles_root / "enabled_pack.json").exists()
    assert (profiles_root / "error_code_registry_snapshot.json").exists()
