from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from orket.extensions.import_guard import ExtensionImportGuard
from orket.extensions.models import CONTRACT_STYLE_SDK_V0, ExtensionRecord, WorkloadRecord
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_executor import WorkloadExecutor

_BLOCKED_MODULE = "orket.runtime.provider_runtime_target"


def _purge_module(module_name: str) -> None:
    for key in list(sys.modules):
        if key == module_name or key.startswith(f"{module_name}."):
            sys.modules.pop(key, None)


def _build_executor(project_root: Path) -> WorkloadExecutor:
    return WorkloadExecutor(
        project_root=project_root,
        reproducibility=ReproducibilityEnforcer(project_root),
        registry_factory=lambda: None,  # type: ignore[arg-type]
    )


def _sdk_records(*, extension_root: Path, module_name: str, workload_id: str) -> tuple[ExtensionRecord, WorkloadRecord]:
    workload = WorkloadRecord(
        workload_id=workload_id,
        workload_version="0.1.0",
        entrypoint=f"{module_name}:run_workload",
        required_capabilities=(),
        contract_style=CONTRACT_STYLE_SDK_V0,
    )
    extension = ExtensionRecord(
        extension_id=f"tests.{workload_id}",
        extension_version="0.1.0",
        source=str(extension_root),
        extension_api_version="v0",
        path=str(extension_root),
        module="",
        register_callable="",
        workloads=(workload,),
        contract_style=CONTRACT_STYLE_SDK_V0,
    )
    return extension, workload


def test_extension_import_guard_prefix_policy() -> None:
    """Layer: unit. Verifies runtime import guard blocks internal `orket.*` and allows SDK namespace."""
    guard = ExtensionImportGuard()
    assert guard.is_blocked("orket.runtime.provider_runtime_target") is True
    assert guard.is_blocked("orket.interfaces.api") is True
    assert guard.is_blocked("orket.extensions.controller_workload_runtime") is False
    assert guard.is_blocked("orket_extension_sdk") is False
    assert guard.is_blocked("orket_extension_sdk.result") is False
    assert guard.is_blocked("json") is False


@pytest.mark.asyncio
async def test_sdk_run_blocks_dynamic_internal_orket_import_and_does_not_leak_guard(tmp_path: Path) -> None:
    """Layer: integration. Verifies runtime guard blocks dynamic host imports during SDK run and is removed after failure."""
    extension_root = tmp_path / "extension"
    extension_root.mkdir(parents=True, exist_ok=True)
    module_name = "sdk_blocking_workload"
    (extension_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import importlib",
                "from orket_extension_sdk.result import WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                f"    importlib.import_module('{_BLOCKED_MODULE}')",
                "    return WorkloadResult(ok=True)",
            ]
        ),
        encoding="utf-8",
    )
    extension, workload = _sdk_records(
        extension_root=extension_root,
        module_name=module_name,
        workload_id="sdk_block_v1",
    )

    executor = _build_executor(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    _purge_module(_BLOCKED_MODULE)
    with pytest.raises(ImportError, match="E_EXT_IMPORT_BLOCKED"):
        await executor.run_sdk_workload(
            extension=extension,
            workload=workload,
            input_config={},
            workspace=workspace,
            department="core",
        )

    assert all(not isinstance(finder, ExtensionImportGuard) for finder in sys.meta_path)

    _purge_module(_BLOCKED_MODULE)
    imported = importlib.import_module(_BLOCKED_MODULE)
    assert imported.__name__ == _BLOCKED_MODULE


@pytest.mark.asyncio
async def test_sdk_run_allows_dynamic_sdk_imports(tmp_path: Path) -> None:
    """Layer: integration. Verifies runtime guard allows dynamic imports from the SDK namespace."""
    extension_root = tmp_path / "extension"
    extension_root.mkdir(parents=True, exist_ok=True)
    module_name = "sdk_allowed_workload"
    (extension_root / f"{module_name}.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "import importlib",
                "from orket_extension_sdk.result import WorkloadResult",
                "",
                "def run_workload(ctx, payload):",
                "    result_mod = importlib.import_module('orket_extension_sdk.result')",
                "    return WorkloadResult(ok=True, output={'module': result_mod.__name__})",
            ]
        ),
        encoding="utf-8",
    )
    extension, workload = _sdk_records(
        extension_root=extension_root,
        module_name=module_name,
        workload_id="sdk_allow_v1",
    )

    executor = _build_executor(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    result = await executor.run_sdk_workload(
        extension=extension,
        workload=workload,
        input_config={},
        workspace=workspace,
        department="core",
    )

    assert result.summary["ok"] is True
    assert all(not isinstance(finder, ExtensionImportGuard) for finder in sys.meta_path)
