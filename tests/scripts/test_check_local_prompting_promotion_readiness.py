from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.check_local_prompting_promotion_readiness import main


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _case_ids(prefix: str, total: int) -> list[str]:
    return [f"{prefix}-{index:04d}" for index in range(total)]


def _build_profile_root(tmp_path: Path, *, provider: str, profile_id: str, template_family: str) -> Path:
    out_root = tmp_path / "artifacts"
    profile_root = out_root / "conformance" / provider / profile_id
    profile_root.mkdir(parents=True, exist_ok=True)

    _write_json(
        profile_root / "strict_json_report.json",
        {
            "schema_version": "local_prompting_conformance.strict_json.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "task_class": "strict_json",
            "total_cases": 1000,
            "pass_cases": 1000,
            "pass_rate": 1.0,
            "strict_ok": True,
            "failure_families": {},
        },
    )
    _write_json(
        profile_root / "tool_call_report.json",
        {
            "schema_version": "local_prompting_conformance.tool_call.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "task_class": "tool_call",
            "total_cases": 500,
            "pass_cases": 500,
            "pass_rate": 1.0,
            "strict_ok": True,
            "failure_families": {},
        },
    )
    _write_json(
        profile_root / "anti_meta_report.json",
        {
            "schema_version": "local_prompting_conformance.anti_meta.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "suite": "promotion",
            "protocol_chatter_rate": 0.0,
            "markdown_fence_rate": 0.0,
            "strict_ok": True,
        },
    )
    _write_json(
        profile_root / "sampling_capabilities.json",
        {
            "schema_version": "local_prompting_sampling_capabilities.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
        },
    )
    _write_json(
        profile_root / "render_verification.json",
        {
            "schema_version": "local_prompting_render_verification.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
        },
    )
    _write_json(
        profile_root / "capability_probe_method.json",
        {
            "schema_version": "local_prompting_capability_probe_method.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "mode": "live",
            "method": "runtime_response_metadata",
        },
    )
    _write_json(
        profile_root / "suite_manifest.json",
        {
            "schema_version": "local_prompting_suite_manifest.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "suite": "promotion",
            "strict_json_case_ids": _case_ids("strict-json", 1000),
            "tool_call_case_ids": _case_ids("tool-call", 500),
        },
    )
    _write_json(
        profile_root / "tokenizer_identity.json",
        {
            "schema_version": "local_prompting_tokenizer_identity.v1",
            "provider": provider,
            "model": "model-a",
            "profile_id": profile_id,
            "tokenizer_source": "profile_declared_equivalent",
        },
    )
    _write_json(
        profile_root / "failure_summary.json",
        {
            "schema_version": "local_prompting_failure_summary.v1",
            "total_failures": 0,
        },
    )
    _write_json(
        out_root / "profiles" / "profile_registry_snapshot.json",
        {
            "schema_version": "local_prompt_profiles.v1",
            "profiles": [
                {
                    "provider": provider,
                    "match": {"model_contains": ["model-a"]},
                    "profile": {
                        "profile_id": profile_id,
                        "template_family": template_family,
                    },
                }
            ],
        },
    )
    _write_json(out_root / "profiles" / "error_code_registry_snapshot.json", {"schema_version": "error_codes.v1"})
    _write_json(out_root / "profiles" / "enabled_pack.json", {"schema_version": "local_prompting_enabled_pack.v1"})
    return profile_root


def test_check_local_prompting_promotion_readiness_passes_on_green_artifacts(tmp_path: Path) -> None:
    profile_root = _build_profile_root(
        tmp_path,
        provider="openai_compat",
        profile_id="openai_compat.qwen.openai_messages.v1",
        template_family="openai_messages",
    )
    drift = tmp_path / "drift.json"
    _write_json(drift, {"schema_version": "local_prompting_profile_drift.v1", "changed": False})
    out = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--profile-root",
            str(profile_root),
            "--drift-report",
            str(drift),
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ready"] is True
    assert payload["profiles"][0]["ready"] is True


def test_check_local_prompting_promotion_readiness_fails_when_strict_json_below_threshold(tmp_path: Path) -> None:
    profile_root = _build_profile_root(
        tmp_path,
        provider="openai_compat",
        profile_id="openai_compat.qwen.openai_messages.v1",
        template_family="openai_messages",
    )
    strict_report = profile_root / "strict_json_report.json"
    payload = json.loads(strict_report.read_text(encoding="utf-8"))
    payload["pass_rate"] = 0.5
    payload["strict_ok"] = False
    _write_json(strict_report, payload)
    drift = tmp_path / "drift.json"
    _write_json(drift, {"schema_version": "local_prompting_profile_drift.v1", "changed": False})
    out = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--profile-root",
            str(profile_root),
            "--drift-report",
            str(drift),
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 1
    readiness = json.loads(out.read_text(encoding="utf-8"))
    gates = {row["id"]: row for row in readiness["profiles"][0]["gates"]}
    assert gates["G3_strict_json_threshold"]["passed"] is False


def test_check_local_prompting_promotion_readiness_requires_template_audit_for_non_openai_profiles(tmp_path: Path) -> None:
    profile_root = _build_profile_root(
        tmp_path,
        provider="ollama",
        profile_id="ollama.qwen.chatml.v1",
        template_family="chatml",
    )
    drift = tmp_path / "drift.json"
    _write_json(drift, {"schema_version": "local_prompting_profile_drift.v1", "changed": False})
    out = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--profile-root",
            str(profile_root),
            "--drift-report",
            str(drift),
            "--template-audit-root",
            str(tmp_path / "missing-template-audit"),
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 1
    readiness = json.loads(out.read_text(encoding="utf-8"))
    gates = {row["id"]: row for row in readiness["profiles"][0]["gates"]}
    assert gates["G8_template_audit_whitelist"]["passed"] is False
