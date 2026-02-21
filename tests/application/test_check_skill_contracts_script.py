from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _valid_manifest() -> dict:
    return {
        "skill_contract_version": "1.0.5",
        "skill_id": "skill.demo",
        "skill_version": "1.2.3",
        "description": "Demo skill",
        "manifest_digest": "sha256:abc123",
        "entrypoints": [
            {
                "entrypoint_id": "main",
                "runtime": "python",
                "runtime_version": "3.11.0",
                "command": "python run.py",
                "working_directory": ".",
                "input_schema": {},
                "output_schema": {},
                "error_schema": {},
                "args_fingerprint_fields": ["input.task"],
                "result_fingerprint_fields": ["result.summary"],
                "side_effect_fingerprint_fields": [],
                "requested_permissions": {},
                "required_permissions": {},
                "tool_profile_id": "tool.demo",
                "tool_profile_version": "1.0.0",
            }
        ],
    }


def test_check_skill_contracts_script_passes_valid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "skill.json"
    manifest.write_text(json.dumps(_valid_manifest()) + "\n", encoding="utf-8")

    result = subprocess.run(
        ["python", "scripts/check_skill_contracts.py", "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_check_skill_contracts_script_fails_invalid_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "skill.json"
    manifest.write_text(json.dumps({"skill_id": "invalid"}) + "\n", encoding="utf-8")
    out = tmp_path / "report.json"

    result = subprocess.run(
        [
            "python",
            "scripts/check_skill_contracts.py",
            "--manifest",
            str(manifest),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert any(item.startswith("schema:") for item in payload["failures"])
