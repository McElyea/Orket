from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.orket_bundle_cli import (
    ERROR_ENGINE_INCOMPATIBLE,
    ERROR_GUARD_FILE_MISSING,
    ERROR_INSPECT_MANIFEST_NOT_FOUND,
    ERROR_MANIFEST_NOT_FOUND,
    ERROR_MANIFEST_SCHEMA,
    ERROR_SDK_COMMAND_REQUIRED,
    ERROR_STATE_MACHINE_MISSING,
    _is_safe_archive_name,
    main,
    validate_bundle,
)
import zipfile
import hashlib


def _fixture_payload(name: str) -> dict:
    path = Path("tests") / "fixtures" / "orket_manifest" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _create_valid_bundle(bundle_root: Path) -> None:
    manifest = _fixture_payload("valid_minimal.json")
    _write_json(bundle_root / "orket.json", manifest)
    _write_json(bundle_root / "state_machine.json", {"initial": "reader"})
    for agent in manifest["agents"]:
        _write_json(bundle_root / "agents" / f"{agent['name']}.json", {"name": agent["name"]})
        (bundle_root / "prompts" / f"{agent['name']}.md").parent.mkdir(parents=True, exist_ok=True)
        (bundle_root / "prompts" / f"{agent['name']}.md").write_text(
            f"# Prompt for {agent['name']}\n",
            encoding="utf-8",
        )
    for guard in manifest["guards"]:
        _write_json(bundle_root / "guards" / f"{guard}.json", {"id": guard})


def test_validate_bundle_success(tmp_path: Path) -> None:
    _create_valid_bundle(tmp_path)
    result = validate_bundle(tmp_path)
    assert result["ok"] is True
    assert result["error_count"] == 0


def test_validate_bundle_manifest_missing(tmp_path: Path) -> None:
    result = validate_bundle(tmp_path)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == ERROR_MANIFEST_NOT_FOUND


def test_validate_bundle_schema_error_is_deterministic(tmp_path: Path) -> None:
    _write_json(tmp_path / "orket.json", _fixture_payload("invalid_missing_permissions.json"))
    result = validate_bundle(tmp_path)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == ERROR_MANIFEST_SCHEMA
    assert result["errors"][0]["location"] == "permissions"


def test_validate_bundle_missing_state_machine_file(tmp_path: Path) -> None:
    _create_valid_bundle(tmp_path)
    (tmp_path / "state_machine.json").unlink()
    result = validate_bundle(tmp_path)
    assert result["ok"] is False
    assert any(item["code"] == ERROR_STATE_MACHINE_MISSING for item in result["errors"])


def test_validate_bundle_missing_guard_file_returns_expected_code(tmp_path: Path) -> None:
    _create_valid_bundle(tmp_path)
    (tmp_path / "guards" / "hallucination.json").unlink()
    result = validate_bundle(tmp_path)
    assert result["ok"] is False
    assert any(item["code"] == ERROR_GUARD_FILE_MISSING for item in result["errors"])


def test_cli_validate_json_exit_code_for_failure(tmp_path: Path, capsys) -> None:
    _write_json(tmp_path / "orket.json", _fixture_payload("invalid_guard_enum.json"))
    code = main(["validate", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == ERROR_MANIFEST_SCHEMA


def test_cli_pack_and_inspect_archive_success(tmp_path: Path, capsys) -> None:
    bundle_dir = tmp_path / "bundle"
    _create_valid_bundle(bundle_dir)
    archive_path = tmp_path / "bundle.orket"

    pack_code = main(["pack", str(bundle_dir), "--out", str(archive_path), "--json"])
    pack_payload = json.loads(capsys.readouterr().out)
    assert pack_code == 0
    assert pack_payload["ok"] is True
    assert archive_path.is_file()

    with zipfile.ZipFile(archive_path, "r") as archive:
        names = set(archive.namelist())
    assert "orket.json" in names
    assert "state_machine.json" in names

    inspect_code = main(["inspect", str(archive_path), "--json"])
    inspect_payload = json.loads(capsys.readouterr().out)
    assert inspect_code == 0
    assert inspect_payload["ok"] is True
    assert inspect_payload["name"] == "orket-summarizer"
    assert inspect_payload["entry_count"] >= 1


def test_cli_inspect_archive_without_manifest_fails(tmp_path: Path, capsys) -> None:
    archive_path = tmp_path / "invalid.orket"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("notes.txt", "missing manifest")

    code = main(["inspect", str(archive_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == ERROR_INSPECT_MANIFEST_NOT_FOUND


def test_cli_pack_is_deterministic_for_same_source(tmp_path: Path, capsys) -> None:
    bundle_dir = tmp_path / "bundle"
    _create_valid_bundle(bundle_dir)
    archive_one = tmp_path / "one.orket"
    archive_two = tmp_path / "two.orket"

    assert main(["pack", str(bundle_dir), "--out", str(archive_one), "--json"]) == 0
    _ = capsys.readouterr()
    assert main(["pack", str(bundle_dir), "--out", str(archive_two), "--json"]) == 0
    _ = capsys.readouterr()

    hash_one = hashlib.sha256(archive_one.read_bytes()).hexdigest()
    hash_two = hashlib.sha256(archive_two.read_bytes()).hexdigest()
    assert hash_one == hash_two


def test_is_safe_archive_name_rejects_path_traversal() -> None:
    assert _is_safe_archive_name("agents/reader.json") is True
    assert _is_safe_archive_name("../escape.txt") is False
    assert _is_safe_archive_name("/absolute.txt") is False
    assert _is_safe_archive_name("nested//double/slash.txt") is False


def test_cli_validate_detects_engine_incompatibility(tmp_path: Path, capsys) -> None:
    _create_valid_bundle(tmp_path)
    code = main(["validate", str(tmp_path), "--engine-version", "0.9.0", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert any(item["code"] == ERROR_ENGINE_INCOMPATIBLE for item in payload["errors"])


def test_cli_validate_rejects_model_override_when_policy_disallows(tmp_path: Path, capsys) -> None:
    _create_valid_bundle(tmp_path)
    manifest_path = tmp_path / "orket.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model"]["allowOverride"] = False
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    code = main(
        [
            "validate",
            str(tmp_path),
            "--available-model",
            "qwen2.5-coder:7b",
            "--model-override",
            "qwen2.5-coder:7b",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert any(item["code"] == "E_MODEL_OVERRIDE_NOT_ALLOWED" for item in payload["errors"])


def test_cli_sdk_version_json(capsys) -> None:
    code = main(["sdk", "--version", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert isinstance(payload["sdk_version"], str)


def test_cli_sdk_requires_command(capsys) -> None:
    code = main(["sdk", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == ERROR_SDK_COMMAND_REQUIRED
