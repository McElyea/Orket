from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orket.extensions.manager import ExtensionManager

PROOF_REF = "python -m pytest -q tests/runtime/test_extension_capability_authorization.py"
HOST_CONTROLS_KEY = "__orket_host_capability_authorization__"

MEMORY_QUERY_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.memory import MemoryQueryRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.memory_query().query(",
        "        MemoryQueryRequest(scope='profile_memory', query='', limit=5)",
        "    )",
        "    return WorkloadResult(ok=response.ok, output={'record_count': len(response.records)})",
    ]
)
MEMORY_WRITE_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.memory import MemoryWriteRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.memory_writer().write(",
        "        MemoryWriteRequest(scope='profile_memory', key='companion_setting.role_id', value='planner')",
        "    )",
        "    return WorkloadResult(ok=response.ok, output={'key': response.key})",
    ]
)
MODEL_GENERATE_SOURCE = "\n".join(
    [
        "from __future__ import annotations",
        "from orket_extension_sdk import WorkloadResult",
        "from orket_extension_sdk.llm import GenerateRequest",
        "",
        "def run_workload(ctx, payload):",
        "    response = ctx.capabilities.llm().generate(",
        "        GenerateRequest(system_prompt='system', user_message='hello world')",
        "    )",
        "    return WorkloadResult(ok=True, output={'text': response.text, 'model': response.model})",
    ]
)


def _init_sdk_repo(repo_root: Path, *, module_source: str, required_capabilities: list[str]) -> None:
    (repo_root / "extension.yaml").write_text(
        "\n".join(
            [
                "manifest_version: v0",
                "extension_id: sdk.auth.extension",
                "extension_version: 0.1.0",
                "allowed_stdlib_modules:",
                "  - pathlib",
                "workloads:",
                "  - workload_id: sdk_auth_v1",
                "    entrypoint: sdk_auth_extension:run_workload",
                f"    required_capabilities: {json.dumps(required_capabilities)}",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "sdk_auth_extension.py").write_text(module_source, encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _host_controls(
    *,
    test_case: str,
    expected_result: str,
    admit_only: list[str] | None = None,
    child_extra_capabilities: list[str] | None = None,
) -> dict[str, object]:
    return {
        HOST_CONTROLS_KEY: {
            "admit_only": list(admit_only or []),
            "child_extra_capabilities": list(child_extra_capabilities or []),
            "audit_case": {
                "test_case": test_case,
                "expected_result": expected_result,
                "proof_ref": PROOF_REF,
            },
        }
    }


def _install_manager(tmp_path: Path, *, module_source: str, required_capabilities: list[str]) -> ExtensionManager:
    repo = tmp_path / "sdk_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_repo(repo, module_source=module_source, required_capabilities=required_capabilities)
    manager = ExtensionManager(catalog_path=tmp_path / "extensions_catalog.json", project_root=tmp_path)
    manager.install_from_repo(str(repo))
    return manager


def _load_provenance(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_provenance(tmp_path: Path) -> dict:
    provenance_paths = sorted((tmp_path / "workspace" / "extensions").rglob("provenance.json"))
    assert provenance_paths
    return _load_provenance(provenance_paths[-1])


def _runtime_event_names(workspace: Path) -> list[str]:
    runtime_events = workspace / "agent_output" / "observability" / "runtime_events.jsonl"
    if not runtime_events.exists():
        return []
    return [json.loads(line)["event"] for line in runtime_events.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.asyncio
async def test_sdk_capability_authorization_allows_admitted_memory_query_without_write(tmp_path: Path) -> None:
    """Layer: integration. Verifies the real subprocess path admits `memory.query` independently of `memory.write`."""
    manager = _install_manager(tmp_path, module_source=MEMORY_QUERY_SOURCE, required_capabilities=["memory.query", "memory.write"])
    workspace = tmp_path / "workspace" / "default"
    result = await manager.run_workload(
        workload_id="sdk_auth_v1",
        input_config=_host_controls(test_case="memory_query_allowed", expected_result="success", admit_only=["memory.query"]),
        workspace=workspace,
        department="core",
    )

    provenance = _load_provenance(Path(result.provenance_path))
    auth = provenance["sdk_capability_authorization"]
    assert auth["admitted_capabilities"] == ["memory.query"]
    assert "memory.query" in auth["used_capabilities"]
    assert "memory.write" not in auth["used_capabilities"]
    assert auth["call_records"][0]["observed_result"] == "success"
    assert "sdk_capability_call_start" in _runtime_event_names(workspace)
    assert "sdk_capability_call_result" in _runtime_event_names(workspace)


@pytest.mark.asyncio
async def test_sdk_capability_authorization_allows_admitted_memory_write_without_read(tmp_path: Path) -> None:
    """Layer: integration. Verifies the real subprocess path admits `memory.write` independently of `memory.query`."""
    manager = _install_manager(tmp_path, module_source=MEMORY_WRITE_SOURCE, required_capabilities=["memory.query", "memory.write"])
    result = await manager.run_workload(
        workload_id="sdk_auth_v1",
        input_config=_host_controls(test_case="memory_write_allowed", expected_result="success", admit_only=["memory.write"]),
        workspace=tmp_path / "workspace" / "default",
        department="core",
    )

    auth = _load_provenance(Path(result.provenance_path))["sdk_capability_authorization"]
    assert auth["admitted_capabilities"] == ["memory.write"]
    assert auth["used_capabilities"] == ["memory.write"]
    assert auth["call_records"][0]["observed_result"] == "success"


@pytest.mark.asyncio
async def test_sdk_capability_authorization_blocks_undeclared_memory_write(tmp_path: Path) -> None:
    """Layer: integration. Verifies undeclared first-slice use fails closed before side effects even when the child has a provider seam."""
    manager = _install_manager(tmp_path, module_source=MEMORY_WRITE_SOURCE, required_capabilities=[])

    with pytest.raises(RuntimeError, match="E_SDK_CAPABILITY_UNDECLARED_USE: memory.write"):
        await manager.run_workload(
            workload_id="sdk_auth_v1",
            input_config=_host_controls(test_case="memory_write_undeclared", expected_result="blocked"),
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )

    auth = _latest_provenance(tmp_path)["sdk_capability_authorization"]
    assert auth["blocked_calls"][0]["denial_class"] == "undeclared_use"
    assert auth["blocked_calls"][0]["side_effect_observed"] is False


@pytest.mark.asyncio
async def test_sdk_capability_authorization_blocks_declared_but_denied_memory_write(tmp_path: Path) -> None:
    """Layer: integration. Verifies declared-but-not-admitted first-slice use stays distinct from undeclared use."""
    manager = _install_manager(tmp_path, module_source=MEMORY_WRITE_SOURCE, required_capabilities=["memory.query", "memory.write"])

    with pytest.raises(RuntimeError, match="E_SDK_CAPABILITY_DENIED: memory.write"):
        await manager.run_workload(
            workload_id="sdk_auth_v1",
            input_config=_host_controls(test_case="memory_write_denied", expected_result="blocked", admit_only=["memory.query"]),
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )

    auth = _latest_provenance(tmp_path)["sdk_capability_authorization"]
    assert auth["blocked_calls"][0]["denial_class"] == "denied"
    assert auth["blocked_calls"][0]["declared"] is True
    assert auth["blocked_calls"][0]["admitted"] is False


@pytest.mark.asyncio
async def test_sdk_capability_authorization_blocks_child_drift_before_workload_execution(tmp_path: Path) -> None:
    """Layer: integration. Verifies the subprocess revalidation fails closed when child-side first-slice authority expands."""
    manager = _install_manager(tmp_path, module_source=MEMORY_QUERY_SOURCE, required_capabilities=["memory.query"])

    with pytest.raises(RuntimeError, match="E_SDK_CAPABILITY_AUTHORIZATION_DRIFT: memory.write"):
        await manager.run_workload(
            workload_id="sdk_auth_v1",
            input_config=_host_controls(
                test_case="child_drift_memory_write",
                expected_result="blocked",
                admit_only=["memory.query"],
                child_extra_capabilities=["memory.write"],
            ),
            workspace=tmp_path / "workspace" / "default",
            department="core",
        )

    auth = _latest_provenance(tmp_path)["sdk_capability_authorization"]
    assert auth["blocked_calls"][0]["denial_class"] == "authorization_drift"
    assert "memory.write" in auth["instantiated_capabilities"]
    assert auth["used_capabilities"] == []


@pytest.mark.asyncio
async def test_sdk_capability_authorization_allows_admitted_model_generate_with_static_provider(tmp_path: Path) -> None:
    """Layer: integration. Verifies the first slice can admit `model.generate` independently using a deterministic host-configured provider."""
    manager = _install_manager(tmp_path, module_source=MODEL_GENERATE_SOURCE, required_capabilities=["model.generate"])
    result = await manager.run_workload(
        workload_id="sdk_auth_v1",
        input_config={
            **_host_controls(test_case="model_generate_allowed", expected_result="success", admit_only=["model.generate"]),
            "capabilities": {"model.generate": {"provider": "static_llm", "text": "static capability proof", "model": "static-model"}},
        },
        workspace=tmp_path / "workspace" / "default",
        department="core",
    )

    provenance = _load_provenance(Path(result.provenance_path))
    auth = provenance["sdk_capability_authorization"]
    assert result.summary["output"]["text"] == "static capability proof"
    assert auth["admitted_capabilities"] == ["model.generate"]
    assert auth["used_capabilities"] == ["model.generate"]
    assert auth["call_records"][0]["capability_id"] == "model.generate"
