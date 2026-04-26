from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import httpx

import orket.interfaces.orket_bundle_cli as cli_module
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


def test_run_submit_cli_uses_api_and_prints_response(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies outward run CLI submits through the API client only."""
    requests: list[dict] = []

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            assert base_url == "http://127.0.0.1:9999"
            assert timeout == 30.0

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            requests.append({"method": method, "path": path, **kwargs})
            request = httpx.Request(method, f"http://127.0.0.1:9999{path}")
            return httpx.Response(200, json={"run_id": "run-cli", "status": "queued"}, request=request)

    monkeypatch.setenv("ORKET_API_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("ORKET_API_KEY", "secret")
    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    code = cli_module.main(["run", "submit", "--description", "Demo", "--instruction", "Do it"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["run_id"] == "run-cli"
    assert requests == [
        {
            "method": "POST",
            "path": "/v1/runs",
            "headers": {"X-API-Key": "secret"},
            "json": {"task": {"description": "Demo", "instruction": "Do it"}},
            "params": None,
        }
    ]


def test_run_status_cli_prints_api_payload(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies outward run status CLI displays the API payload."""

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            request = httpx.Request(method, f"http://127.0.0.1:8082{path}")
            return httpx.Response(
                200,
                json={"run_id": "run-cli", "status": "queued", "current_turn": 0},
                request=request,
            )

    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    code = cli_module.main(["run", "status", "run-cli"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload == {"run_id": "run-cli", "status": "queued", "current_turn": 0}


def test_run_list_cli_sends_status_filter(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies outward run list CLI delegates filtering to the API."""
    requests: list[dict] = []

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            requests.append({"method": method, "path": path, **kwargs})
            request = httpx.Request(method, f"http://127.0.0.1:8082{path}")
            return httpx.Response(200, json={"items": [], "count": 0}, request=request)

    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    code = cli_module.main(["run", "list", "--status", "queued"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload == {"items": [], "count": 0}
    assert requests[0]["method"] == "GET"
    assert requests[0]["path"] == "/v1/runs"
    assert requests[0]["params"] == {"status": "queued", "limit": 20, "offset": 0}


def test_approvals_cli_delegates_list_review_and_decisions(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies outward approvals CLI commands are API-client wrappers."""
    requests: list[dict] = []
    monkeypatch.delenv("ORKET_API_KEY", raising=False)

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            requests.append({"method": method, "path": path, **kwargs})
            request = httpx.Request(method, f"http://127.0.0.1:8082{path}")
            return httpx.Response(200, json={"ok": True, "path": path}, request=request)

    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    assert cli_module.main(["approvals", "list"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["approvals", "review", "proposal-1"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["approvals", "approve", "proposal-1", "--note", "safe"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["approvals", "deny", "proposal-2", "--reason", "unsafe"]) == 0
    _ = json.loads(capsys.readouterr().out)

    assert requests == [
        {
            "method": "GET",
            "path": "/v1/approvals",
            "headers": {},
            "json": None,
            "params": {"status": "pending"},
        },
        {
            "method": "GET",
            "path": "/v1/approvals/proposal-1",
            "headers": {},
            "json": None,
            "params": None,
        },
        {
            "method": "POST",
            "path": "/v1/approvals/proposal-1/approve",
            "headers": {},
            "json": {"note": "safe"},
            "params": None,
        },
        {
            "method": "POST",
            "path": "/v1/approvals/proposal-2/deny",
            "headers": {},
            "json": {"reason": "unsafe", "note": None},
            "params": None,
        },
    ]


def test_run_inspection_cli_delegates_events_summary_and_watch(monkeypatch, capsys) -> None:
    """Layer: contract. Verifies outward run inspection CLI commands are API-client wrappers."""
    requests: list[dict] = []
    monkeypatch.delenv("ORKET_API_KEY", raising=False)

    class _FakeClient:
        def __init__(self, *, base_url: str, timeout: float) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb) -> None:
            return None

        def request(self, method: str, path: str, **kwargs):
            requests.append({"method": method, "path": path, **kwargs})
            request = httpx.Request(method, f"http://127.0.0.1:8082{path}")
            return httpx.Response(200, json={"ok": True, "path": path}, request=request)

    monkeypatch.setattr(cli_module.httpx, "Client", _FakeClient)

    assert cli_module.main(["run", "events", "run-1", "--types", "tool_invoked", "--from-turn", "1"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["run", "summary", "run-1"]) == 0
    _ = json.loads(capsys.readouterr().out)
    assert cli_module.main(["run", "watch", "run-1", "--types", "run_completed"]) == 0
    _ = json.loads(capsys.readouterr().out)

    assert requests == [
        {
            "method": "GET",
            "path": "/v1/runs/run-1/events",
            "headers": {},
            "json": None,
            "params": {"types": "tool_invoked", "from_turn": 1},
        },
        {
            "method": "GET",
            "path": "/v1/runs/run-1/summary",
            "headers": {},
            "json": None,
            "params": None,
        },
        {
            "method": "GET",
            "path": "/v1/runs/run-1/events/stream",
            "headers": {},
            "json": None,
            "params": {"types": "run_completed"},
        },
    ]


def test_connectors_cli_lists_shows_and_tests_local_harness(tmp_path: Path, capsys) -> None:
    """Layer: contract. Verifies built-in connector CLI uses the local Phase 5 harness."""
    list_code = cli_module.main(["connectors", "list", "--workspace", str(tmp_path)])
    listed = json.loads(capsys.readouterr().out)
    show_code = cli_module.main(["connectors", "show", "write_file", "--workspace", str(tmp_path)])
    shown = json.loads(capsys.readouterr().out)
    test_code = cli_module.main(
        [
            "connectors",
            "test",
            "create_directory",
            "--args",
            json.dumps({"path": "made"}),
            "--workspace",
            str(tmp_path),
        ]
    )
    tested = json.loads(capsys.readouterr().out)

    assert list_code == 0
    assert {item["name"] for item in listed["items"]} >= {"write_file", "delete_file", "http_get", "run_command"}
    assert show_code == 0
    assert shown["name"] == "write_file"
    assert test_code == 0
    assert set(tested) == {"connector_name", "args_hash", "result_summary", "duration_ms", "outcome"}
    assert tested["outcome"] == "success"
    assert (tmp_path / "made").is_dir()


def test_connectors_cli_rejects_invalid_args_before_harness_invocation(tmp_path: Path, capsys) -> None:
    """Layer: contract. Verifies connector CLI reports field-level validation errors."""
    code = cli_module.main(
        [
            "connectors",
            "test",
            "write_file",
            "--args",
            json.dumps({"path": "missing-content.txt"}),
            "--workspace",
            str(tmp_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 1
    assert payload["code"] == cli_module.ERROR_CONNECTOR_FAILED
    assert payload["errors"] == [{"field": "content", "reason": "required"}]
    assert (tmp_path / "missing-content.txt").exists() is False
