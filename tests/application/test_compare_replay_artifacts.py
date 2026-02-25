from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_compare_replay_artifacts_ignores_volatile_fields(tmp_path: Path) -> None:
    module = _load_script_module("compare_replay_artifacts_a", "scripts/compare_replay_artifacts.py")

    left = {
        "contract_version": "core_pillars/replay_artifact/v1",
        "recorded_at": "2026-02-24T08:00:00+00:00",
        "artifact_id": "a" * 64,
        "command": "api_add",
        "request": {"name": "users"},
        "result": {"ok": True, "code": "OK", "message": "ok"},
    }
    right = {
        "contract_version": "core_pillars/replay_artifact/v1",
        "recorded_at": "2026-02-24T09:00:00+00:00",
        "artifact_id": "b" * 64,
        "command": "api_add",
        "request": {"name": "users"},
        "result": {"ok": True, "code": "OK", "message": "ok"},
    }
    mismatches: list[dict[str, str]] = []
    module._compare_values(left=left, right=right, path="", mismatches=mismatches)

    assert mismatches == []


def test_compare_replay_artifacts_reports_deterministic_mismatch_order(tmp_path: Path) -> None:
    module = _load_script_module("compare_replay_artifacts_b", "scripts/compare_replay_artifacts.py")

    left = {
        "contract_version": "core_pillars/replay_artifact/v1",
        "command": "api_add",
        "request": {"z": 1, "a": [1, 2]},
        "result": {"ok": True, "message": "left"},
    }
    right = {
        "contract_version": "core_pillars/replay_artifact/v1",
        "command": "refactor",
        "request": {"z": 2, "a": [1]},
        "result": {"ok": False, "message": "right"},
    }
    mismatches: list[dict[str, str]] = []
    module._compare_values(left=left, right=right, path="", mismatches=mismatches)
    ordered = sorted(mismatches, key=lambda item: (item.get("field", ""), item.get("reason", "")))

    assert [item["field"] for item in ordered] == ["command", "request.a", "request.z", "result.message", "result.ok"]


def test_compare_replay_artifacts_cli_writes_fail_report(tmp_path: Path, monkeypatch: object) -> None:
    module = _load_script_module("compare_replay_artifacts_c", "scripts/compare_replay_artifacts.py")

    left_path = tmp_path / "left.json"
    right_path = tmp_path / "right.json"
    out_path = tmp_path / "report.json"
    _write(
        left_path,
        {
            "contract_version": "core_pillars/replay_artifact/v1",
            "command": "api_add",
            "request": {"name": "users"},
            "result": {"ok": True, "code": "OK", "message": "ok"},
        },
    )
    _write(
        right_path,
        {
            "contract_version": "core_pillars/replay_artifact/v1",
            "command": "api_add",
            "request": {"name": "accounts"},
            "result": {"ok": True, "code": "OK", "message": "ok"},
        },
    )

    monkeypatch.setattr(
        module,
        "_parse_args",
        lambda: module.argparse.Namespace(left=str(left_path), right=str(right_path), out=str(out_path)),
    )
    rc = module.main()
    report = json.loads(out_path.read_text(encoding="utf-8"))

    assert rc == 2
    assert report["status"] == "FAIL"
    assert report["mismatch_count"] == 1
    assert report["summary"] == ["request.name: value_mismatch"]
