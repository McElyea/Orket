from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.runtime_context import OrketRuntimeContext

pytestmark = pytest.mark.unit


class _FakeLoader:
    def __init__(self, root: Path, department: str = "core", **_kwargs) -> None:
        self.root = root
        self.department = department

    def load_organization(self):
        return None


def test_runtime_context_resolves_engine_config_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ORKET_RUN_LEDGER_MODE", raising=False)
    seen: dict[str, object] = {}

    def _resolve_config_root(config_root: Path | None) -> Path:
        seen["config_root"] = config_root
        return tmp_path / "resolved-config"

    def _fake_run_ledger_factory(**kwargs):
        seen["ledger_kwargs"] = kwargs
        return object()

    async def _telemetry(_payload: dict[str, object]) -> None:
        return None

    context = OrketRuntimeContext.from_env(
        workspace_root=tmp_path,
        config_root=tmp_path / "incoming-config",
        config_loader_factory=_FakeLoader,
        config_root_resolver=_resolve_config_root,
        run_ledger_factory=_fake_run_ledger_factory,
        telemetry_sink=_telemetry,
    )

    assert context.config_root == tmp_path / "resolved-config"
    assert seen["config_root"] == tmp_path / "incoming-config"
    assert seen["ledger_kwargs"]["workspace_root"] == tmp_path
    assert context.run_ledger_mode == "sqlite"
