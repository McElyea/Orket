from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from orket.extensions import ExtensionManager


def _load_register_module():
    script_path = Path("scripts/register_meta_breaker_extension.py").resolve()
    spec = importlib.util.spec_from_file_location("register_meta_breaker_extension_for_run", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load register_meta_breaker_extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_run_meta_breaker_workload_is_deterministic_for_same_seed(tmp_path, monkeypatch):
    module = _load_register_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    durable_root = tmp_path / ".orket_durable"
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(durable_root))
    assert module.main() == 0

    manager = ExtensionManager(project_root=tmp_path)
    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    result_a = await manager.run_workload(
        workload_id="meta_breaker_v1",
        input_config={"seed": 17, "first_player_advantage": 0.02, "dominant_threshold": 0.55},
        workspace=workspace,
        department="core",
    )
    result_b = await manager.run_workload(
        workload_id="meta_breaker_v1",
        input_config={"seed": 17, "first_player_advantage": 0.02, "dominant_threshold": 0.55},
        workspace=workspace,
        department="core",
    )

    assert result_a.workload_id == "meta_breaker_v1"
    assert result_b.workload_id == "meta_breaker_v1"
    assert result_a.plan_hash == result_b.plan_hash
    assert result_a.summary["output"] == result_b.summary["output"]
    assert Path(result_a.provenance_path).exists()
    assert Path(result_b.provenance_path).exists()
