from __future__ import annotations

# Layer: unit/integration
from pathlib import Path

import pytest

from orket.extensions.manager import ExtensionManager
from orket.runtime.controller_replay_parity import compare_controller_replay_outputs
from scripts.extensions.bootstrap_controller_external_repo import bootstrap_controller_external_repo
from tests.runtime.test_controller_dispatcher import _init_git_repo, _init_sdk_child_repo
from tests.runtime.test_controller_observability import _build_controller_manager


def test_compare_controller_replay_outputs_detects_status_drift() -> None:
    """Layer: unit."""
    expected = {
        "controller_summary": {
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "status": "success",
            "error_code": None,
            "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
            "enforced_caps": {"max_depth": 1, "max_fanout": 5, "child_timeout_seconds": 30},
            "child_results": [
                {
                    "target_workload": "sdk_child_a_v1",
                    "status": "success",
                    "requested_timeout": 30,
                    "enforced_timeout": 30,
                    "normalized_error": None,
                    "summary": {"ok": True},
                }
            ],
        },
        "controller_observability_projection": [
            {"event": "controller_run", "result": "success", "error_code": None},
            {"event": "controller_child", "child_index": 0, "status": "success", "error_code": None},
        ],
    }
    actual = {
        "controller_summary": {
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "status": "failed",
            "error_code": "controller.child_execution_failed",
            "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
            "enforced_caps": {"max_depth": 1, "max_fanout": 5, "child_timeout_seconds": 30},
            "child_results": [
                {
                    "target_workload": "sdk_child_a_v1",
                    "status": "failed",
                    "requested_timeout": 30,
                    "enforced_timeout": 30,
                    "normalized_error": "controller.child_execution_failed",
                    "summary": {"ok": False},
                }
            ],
        },
        "controller_observability_projection": [
            {"event": "controller_run", "result": "failed", "error_code": "controller.child_execution_failed"},
            {
                "event": "controller_child",
                "child_index": 0,
                "status": "failure",
                "error_code": "controller.child_execution_failed",
            },
        ],
    }
    report = compare_controller_replay_outputs(expected_output=expected, actual_output=actual)

    assert report["parity_ok"] is False
    assert report["difference_count"] >= 1
    assert any(item["path"] == "$.controller_summary.status" for item in report["differences"])
    assert report["expected_digest"] != report["actual_digest"]


@pytest.mark.asyncio
async def test_compare_controller_replay_outputs_passes_for_equivalent_controller_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Layer: integration."""
    manager, workspace = _build_controller_manager(tmp_path, monkeypatch)
    payload_a = {
        "controller_workload_id": "controller_workload_v1",
        "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
        "children": [
            {"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0", "payload": {"token": "a"}},
            {"target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0", "payload": {"token": "b"}},
        ],
    }
    payload_b = {
        "requested_caps": {"child_timeout_seconds": 30, "max_fanout": 5, "max_depth": 2},
        "children": [
            {"payload": {"token": "a"}, "contract_style": "sdk_v0", "target_workload": "sdk_child_a_v1"},
            {"target_workload": "sdk_child_b_v1", "payload": {"token": "b"}, "contract_style": "sdk_v0"},
        ],
        "controller_workload_id": "controller_workload_v1",
    }
    run_a = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config=payload_a,
        workspace=workspace,
        department="core",
    )
    run_b = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config=payload_b,
        workspace=workspace,
        department="core",
    )
    report = compare_controller_replay_outputs(
        expected_output=run_a.summary["output"],
        actual_output=run_b.summary["output"],
    )

    assert report["parity_ok"] is True
    assert report["differences"] == []
    assert report["expected_digest"] == report["actual_digest"]


@pytest.mark.asyncio
async def test_external_template_repo_installs_and_runs_controller_workload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Layer: integration."""
    catalog_path = tmp_path / "extensions_catalog.json"
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))

    sdk_a = tmp_path / "sdk_a"
    sdk_b = tmp_path / "sdk_b"
    controller_external = tmp_path / "controller_external"
    for repo in (sdk_a, sdk_b, controller_external):
        repo.mkdir(parents=True, exist_ok=True)

    _init_sdk_child_repo(sdk_a, extension_id="sdk.child.a", workload_id="sdk_child_a_v1")
    _init_sdk_child_repo(sdk_b, extension_id="sdk.child.b", workload_id="sdk_child_b_v1")
    bootstrap_controller_external_repo(target_dir=controller_external, force=True)
    _init_git_repo(controller_external)

    manager = ExtensionManager(catalog_path=catalog_path, project_root=tmp_path)
    manager.install_from_repo(str(sdk_a))
    manager.install_from_repo(str(sdk_b))
    manager.install_from_repo(str(controller_external))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    run = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
            "children": [
                {"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0", "payload": {"token": "a"}},
                {"target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0", "payload": {"token": "b"}},
            ],
        },
        workspace=workspace,
        department="core",
    )
    output = run.summary["output"]
    assert output["controller_summary"]["status"] == "success"
    assert output["controller_summary"]["error_code"] is None
