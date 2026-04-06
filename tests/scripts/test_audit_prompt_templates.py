# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.protocol.audit_prompt_templates import main


def _registry_payload(variant: str, template_source_path: str = "") -> dict[str, object]:
    profile: dict[str, object] = {
        "profile_id": "ollama.deepseek.custom.v1",
        "template_family": "custom",
        "template_variant": variant,
        "template_source": "profile_override",
        "template_version": "v1",
    }
    if template_source_path:
        profile["template_source_path"] = template_source_path
    return {
        "schema_version": "local_prompt_profiles.v1",
        "profiles": [
            {
                "provider": "ollama",
                "match": {"model_contains": ["deepseek"]},
                "profile": profile,
            }
        ],
    }


def test_audit_prompt_templates_strict_fails_on_suspicious_construct(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    out_root = tmp_path / "artifacts"
    registry.write_text(json.dumps(_registry_payload("jinja_eval_importlib")), encoding="utf-8")

    exit_code = main(["--registry", str(registry), "--out-root", str(out_root), "--strict"])
    assert exit_code == 1

    audit_path = out_root / "template_audit" / "ollama.deepseek.custom.v1" / "audit_report.json"
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "fail"
    assert payload["detected_constructs"]


def test_audit_prompt_templates_whitelist_allows_promotion(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    whitelist = tmp_path / "whitelist.json"
    out_root = tmp_path / "artifacts"
    registry.write_text(json.dumps(_registry_payload("jinja_eval_importlib")), encoding="utf-8")
    whitelist.write_text(
        json.dumps({"approved_profile_ids": ["ollama.deepseek.custom.v1"]}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--registry",
            str(registry),
            "--whitelist",
            str(whitelist),
            "--out-root",
            str(out_root),
            "--strict",
        ]
    )
    assert exit_code == 0

    decision_path = out_root / "template_audit" / "ollama.deepseek.custom.v1" / "whitelist_decision.json"
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    assert payload["approved"] is True
    assert payload["promotion_allowed"] is True


def test_audit_prompt_templates_scans_template_source_file(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    out_root = tmp_path / "artifacts"
    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "profile.jinja"
    template_path.write_text("{{ self.__init__.__globals__ }}", encoding="utf-8")
    registry.write_text(
        json.dumps(_registry_payload("jinja_clean", template_source_path="templates/profile.jinja")),
        encoding="utf-8",
    )

    exit_code = main(["--registry", str(registry), "--out-root", str(out_root), "--strict"])
    assert exit_code == 1

    audit_path = out_root / "template_audit" / "ollama.deepseek.custom.v1" / "audit_report.json"
    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert "jinja_globals_escape" in payload["detected_constructs"]
    assert payload["template_sources_loaded"] == [str(template_path.resolve())]
