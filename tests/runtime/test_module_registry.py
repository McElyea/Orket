from __future__ import annotations

import pytest

from orket.runtime import module_registry
from orket.runtime.composition import CompositionConfig, create_api_app, create_engine


def test_resolve_module_profile_defaults_to_developer_local(monkeypatch):
    monkeypatch.delenv("ORKET_MODULE_PROFILE", raising=False)
    monkeypatch.setattr(module_registry, "load_user_settings", lambda: {})
    assert module_registry.resolve_module_profile() == "developer-local"


def test_resolve_module_profile_prefers_env(monkeypatch):
    monkeypatch.setenv("ORKET_MODULE_PROFILE", "api-runtime")
    monkeypatch.setattr(module_registry, "load_user_settings", lambda: {"module_profile": "engine-only"})
    assert module_registry.resolve_module_profile() == "api-runtime"


def test_modules_for_profile_unknown_raises():
    with pytest.raises(module_registry.ModuleResolutionError) as exc:
        module_registry.modules_for_profile("unknown-profile")
    assert exc.value.code == "E_MODULE_PROFILE_UNKNOWN"


def test_ensure_capability_disabled_by_profile_raises():
    with pytest.raises(module_registry.ModuleResolutionError) as exc:
        module_registry.ensure_capability_enabled("api.http.v1", profile="engine-only")
    assert exc.value.code == "E_CAPABILITY_DISABLED_BY_PROFILE"
    payload = exc.value.to_payload()
    assert payload["ok"] is False
    assert payload["code"] == "E_CAPABILITY_DISABLED_BY_PROFILE"


def test_create_engine_uses_factory_with_engine_profile(monkeypatch):
    import orket.orchestration.engine as engine_module

    captured = {}

    class _FakeEngine:
        def __init__(self, workspace):
            captured["workspace"] = workspace

    monkeypatch.setattr(engine_module, "OrchestrationEngine", _FakeEngine)
    engine = create_engine(
        CompositionConfig(
            workspace_root=None,
            module_profile="engine-only",
        )
    )
    assert isinstance(engine, _FakeEngine)
    assert str(captured["workspace"]).endswith("workspace\\default")


def test_create_api_app_rejects_engine_only_profile():
    with pytest.raises(module_registry.ModuleResolutionError) as exc:
        create_api_app(CompositionConfig(module_profile="engine-only"))
    assert exc.value.code == "E_CAPABILITY_DISABLED_BY_PROFILE"


def test_ensure_module_enabled_contract_incompatible():
    manifests = module_registry.built_in_manifests()
    manifests["api"] = manifests["api"].model_copy(update={"contract_version_range": ">=2.0.0,<3.0.0"})
    with pytest.raises(module_registry.ModuleResolutionError) as exc:
        module_registry.ensure_module_enabled("api", profile="api-runtime", manifests=manifests)
    assert exc.value.code == "E_MODULE_CONTRACT_INCOMPATIBLE"
