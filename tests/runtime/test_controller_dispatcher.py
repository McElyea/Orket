from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from orket.extensions.controller_dispatcher import (
    ERROR_CHILD_EXECUTION_FAILED,
    ERROR_CHILD_SDK_REQUIRED,
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_CYCLE_DENIED,
    ERROR_MAX_DEPTH_EXCEEDED,
    ERROR_MAX_FANOUT_EXCEEDED,
    ERROR_RECURSION_DENIED,
    ControllerDispatcher,
)
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import CONTRACT_STYLE_SDK_V0, ExtensionRunResult
from orket_extension_sdk.controller import ControllerPolicyCaps


def _extension_result(workload_id: str, *, ok: bool, suffix: str) -> ExtensionRunResult:
    return ExtensionRunResult(
        extension_id=f"ext.{workload_id}",
        extension_version="0.1.0",
        workload_id=workload_id,
        workload_version="0.1.0",
        plan_hash=f"plan-{suffix}",
        artifact_root=f"artifact/{suffix}",
        provenance_path=f"artifact/{suffix}/provenance.json",
        summary={"ok": ok, "status": "ok" if ok else "error"},
    )


class _StubExtensionManager:
    def __init__(
        self,
        *,
        workload_styles: dict[str, str],
        outcomes: dict[str, list[ExtensionRunResult | Exception]],
    ) -> None:
        self._workload_styles = workload_styles
        self._outcomes = outcomes
        self.calls: list[str] = []

    def has_manifest_entry(self, workload_id: str) -> bool:
        return workload_id in self._workload_styles

    def uses_sdk_contract(self, workload_id: str) -> bool:
        return self._workload_styles.get(workload_id) == CONTRACT_STYLE_SDK_V0

    async def run_workload(
        self,
        *,
        workload_id: str,
        input_config: dict[str, object],
        workspace: Path,
        department: str,
        interaction_context: object | None = None,
    ) -> ExtensionRunResult:
        _ = (input_config, workspace, department, interaction_context)
        self.calls.append(workload_id)
        options = self._outcomes.get(workload_id) or []
        if not options:
            raise RuntimeError("no stub outcome configured")
        outcome = options.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_sdk_child_repo(repo_root: Path, *, extension_id: str, workload_id: str) -> None:
    manifest = {
        "manifest_version": "v0",
        "extension_id": extension_id,
        "extension_version": "0.1.0",
        "allowed_stdlib_modules": ["hashlib", "pathlib"],
        "workloads": [
            {
                "workload_id": workload_id,
                "entrypoint": "sdk_child:run_workload",
                "required_capabilities": [],
            }
        ],
    }
    (repo_root / "extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "sdk_child.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import hashlib",
                "from pathlib import Path",
                "from orket_extension_sdk import ArtifactRef, Issue, WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                "    out = Path(ctx.output_dir) / 'child.txt'",
                "    text = f\"{ctx.workload_id}:{payload.get('token', '')}\"",
                "    out.write_text(text, encoding='utf-8')",
                "    digest = hashlib.sha256(out.read_bytes()).hexdigest()",
                "    if payload.get('fail'):",
                "        return WorkloadResult(ok=False, output={'workload_id': ctx.workload_id}, issues=[Issue(code='child.failed', message='fail')])",
                "    return WorkloadResult(",
                "        ok=True,",
                "        output={'workload_id': ctx.workload_id, 'token': payload.get('token', '')},",
                "        artifacts=[ArtifactRef(path='child.txt', digest_sha256=digest, kind='text')],",
                "    )",
            ]
        ),
        encoding="utf-8",
    )
    _init_git_repo(repo_root)


def _init_legacy_repo(repo_root: Path, *, extension_id: str, workload_id: str) -> None:
    manifest = {
        "extension_id": extension_id,
        "extension_version": "1.0.0",
        "extension_api_version": "1.0.0",
        "module": "legacy_extension",
        "register_callable": "register",
        "workloads": [{"workload_id": workload_id, "workload_version": "1.0.0"}],
    }
    (repo_root / "orket_extension.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (repo_root / "legacy_extension.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "from orket.extensions import RunPlan",
                "",
                "class LegacyWorkload:",
                "    workload_id = 'legacy_child_v1'",
                "    workload_version = '1.0.0'",
                "    def compile(self, input_config):",
                "        _ = input_config",
                "        return RunPlan(workload_id='legacy_child_v1', workload_version='1.0.0', actions=())",
                "    def validators(self):",
                "        return []",
                "    def summarize(self, run_artifacts):",
                "        return {'ok': True, 'run_artifacts': sorted(run_artifacts.keys())}",
                "    def required_materials(self):",
                "        return []",
                "",
                "def register(registry):",
                "    registry.register_workload(LegacyWorkload())",
            ]
        ),
        encoding="utf-8",
    )
    _init_git_repo(repo_root)


def _init_controller_bootstrap_repo(repo_root: Path) -> None:
    source = Path("extensions") / "controller_workload"
    for name in ("manifest.json", "extension.json", "workload_entrypoint.py"):
        shutil.copy2(source / name, repo_root / name)
    _init_git_repo(repo_root)


@pytest.mark.asyncio
async def test_controller_dispatcher_caps_and_stop_on_first_failure() -> None:
    """Layer: unit."""
    manager = _StubExtensionManager(
        workload_styles={"sdk_a": CONTRACT_STYLE_SDK_V0, "sdk_b": CONTRACT_STYLE_SDK_V0, "sdk_c": CONTRACT_STYLE_SDK_V0},
        outcomes={
            "sdk_a": [_extension_result("sdk_a", ok=True, suffix="a")],
            "sdk_b": [_extension_result("sdk_b", ok=False, suffix="b")],
            "sdk_c": [_extension_result("sdk_c", ok=True, suffix="c")],
        },
    )
    dispatcher = ControllerDispatcher(
        extension_manager=manager,
        runtime_policy_caps=ControllerPolicyCaps(max_depth=1, max_fanout=5, child_timeout_seconds=10),
    )
    summary = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": [],
            "requested_caps": {"max_depth": 3, "max_fanout": 9, "child_timeout_seconds": 99},
            "children": [
                {"target_workload": "sdk_a", "contract_style": "sdk_v0", "timeout_seconds": 50},
                {"target_workload": "sdk_b", "contract_style": "sdk_v0"},
                {"target_workload": "sdk_c", "contract_style": "sdk_v0"},
            ],
        },
        workspace=Path(),
        department="core",
    )
    assert summary.status == "failed"
    assert summary.error_code == ERROR_CHILD_EXECUTION_FAILED
    assert summary.requested_caps is not None and summary.requested_caps.max_fanout == 9
    assert summary.enforced_caps is not None and summary.enforced_caps.max_fanout == 5
    assert [row.status for row in summary.child_results] == ["success", "failed", "not_attempted"]
    assert summary.child_results[0].enforced_timeout == 10
    assert manager.calls == ["sdk_a", "sdk_b"]


@pytest.mark.asyncio
async def test_controller_dispatcher_depth_recursion_cycle_and_timeout_validation() -> None:
    """Layer: unit."""
    manager = _StubExtensionManager(
        workload_styles={"sdk_a": CONTRACT_STYLE_SDK_V0, "legacy_a": "legacy_v1"},
        outcomes={"sdk_a": [_extension_result("sdk_a", ok=True, suffix="a")]},
    )
    dispatcher = ControllerDispatcher(extension_manager=manager)

    depth = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 1,
            "ancestry": [],
            "requested_caps": {"max_depth": 1},
            "children": [{"target_workload": "sdk_a", "contract_style": "sdk_v0"}],
        },
        workspace=Path(),
        department="core",
    )
    assert depth.error_code == ERROR_MAX_DEPTH_EXCEEDED

    recursion = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": ["controller_workload_v1"],
            "children": [{"target_workload": "sdk_a", "contract_style": "sdk_v0"}],
        },
        workspace=Path(),
        department="core",
    )
    assert recursion.error_code == ERROR_RECURSION_DENIED

    cycle = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": ["root"],
            "children": [
                {"target_workload": "root", "contract_style": "sdk_v0"},
                {"target_workload": "sdk_a", "contract_style": "sdk_v0"},
            ],
        },
        workspace=Path(),
        department="core",
    )
    assert cycle.error_code == ERROR_CYCLE_DENIED
    assert [row.status for row in cycle.child_results] == ["failed", "not_attempted"]

    legacy = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": [],
            "children": [{"target_workload": "legacy_a", "contract_style": "sdk_v0"}],
        },
        workspace=Path(),
        department="core",
    )
    assert legacy.error_code == ERROR_CHILD_SDK_REQUIRED

    timeout_invalid = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": [],
            "children": [{"target_workload": "sdk_a", "contract_style": "sdk_v0", "timeout_seconds": 0}],
        },
        workspace=Path(),
        department="core",
    )
    assert timeout_invalid.error_code == ERROR_CHILD_TIMEOUT_INVALID


@pytest.mark.asyncio
async def test_controller_dispatcher_integration_runtime_path_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration."""
    catalog_path = tmp_path / "extensions_catalog.json"
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))

    sdk_a = tmp_path / "sdk_a"
    sdk_b = tmp_path / "sdk_b"
    legacy = tmp_path / "legacy"
    controller = tmp_path / "controller"
    for repo in (sdk_a, sdk_b, legacy, controller):
        repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_child_repo(sdk_a, extension_id="sdk.child.a", workload_id="sdk_child_a_v1")
    _init_sdk_child_repo(sdk_b, extension_id="sdk.child.b", workload_id="sdk_child_b_v1")
    _init_legacy_repo(legacy, extension_id="legacy.child", workload_id="legacy_child_v1")
    _init_controller_bootstrap_repo(controller)

    manager = ExtensionManager(catalog_path=catalog_path, project_root=tmp_path)
    manager.install_from_repo(str(sdk_a))
    manager.install_from_repo(str(sdk_b))
    manager.install_from_repo(str(legacy))
    manager.install_from_repo(str(controller))

    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    base_payload = {
        "controller_workload_id": "controller_workload_v1",
        "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
        "children": [
            {"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0", "payload": {"token": "a"}},
            {"target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0", "payload": {"token": "b"}},
        ],
        "extensions_catalog_path": str(catalog_path),
    }

    success_one = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config=base_payload,
        workspace=workspace,
        department="core",
    )
    success_two = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "children": [
                {"contract_style": "sdk_v0", "target_workload": "sdk_child_a_v1", "payload": {"token": "a"}},
                {"payload": {"token": "b"}, "target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0"},
            ],
            "requested_caps": {"child_timeout_seconds": 30, "max_fanout": 5, "max_depth": 2},
            "extensions_catalog_path": str(catalog_path),
        },
        workspace=workspace,
        department="core",
    )
    out_one = success_one.summary["output"]["controller_summary"]
    out_two = success_two.summary["output"]["controller_summary"]
    assert out_one["status"] == "success"
    assert [row["target_workload"] for row in out_one["child_results"]] == ["sdk_child_a_v1", "sdk_child_b_v1"]
    assert success_one.summary["output"]["controller_summary_canonical"] == success_two.summary["output"]["controller_summary_canonical"]
    assert out_one == out_two

    legacy_denial = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "children": [{"target_workload": "legacy_child_v1", "contract_style": "sdk_v0"}],
            "extensions_catalog_path": str(catalog_path),
        },
        workspace=workspace,
        department="core",
    )
    assert legacy_denial.summary["output"]["controller_summary"]["error_code"] == ERROR_CHILD_SDK_REQUIRED

    fanout_denial = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "requested_caps": {"max_fanout": 1},
            "children": [
                {"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"},
                {"target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0"},
            ],
            "extensions_catalog_path": str(catalog_path),
        },
        workspace=workspace,
        department="core",
    )
    assert fanout_denial.summary["output"]["controller_summary"]["error_code"] == ERROR_MAX_FANOUT_EXCEEDED

    depth_denial = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 1,
            "requested_caps": {"max_depth": 1},
            "children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}],
            "extensions_catalog_path": str(catalog_path),
        },
        workspace=workspace,
        department="core",
    )
    assert depth_denial.summary["output"]["controller_summary"]["error_code"] == ERROR_MAX_DEPTH_EXCEEDED

    cycle_denial = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "ancestry": ["sdk_child_a_v1"],
            "children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}],
            "extensions_catalog_path": str(catalog_path),
        },
        workspace=workspace,
        department="core",
    )
    assert cycle_denial.summary["output"]["controller_summary"]["error_code"] == ERROR_CYCLE_DENIED
