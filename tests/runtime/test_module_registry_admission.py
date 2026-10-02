"""Public module admission contracts; no runtime construction is claimed."""
from contextvars import copy_context

import pytest

from orket.core.domain.module_manifest import ModuleManifest
from orket.runtime.registry.module_registry import (
    ModuleResolutionError,
    built_in_manifests,
    ensure_capability_enabled,
    ensure_module_enabled,
    profiles,
    resolve_module_profile,
)
from orket.settings import set_runtime_settings_context

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("constraint,allowed", [
    ("", False), (">1.0.0", False), (">0.9.0", True),
    ("<=0.9.0", False), ("<=1.0.0", True), ("<1.0.0", False),
    ("<2.0.0", True), ("==2.0.0", False), ("==1", True), ("==malformed", False),
])
def test_contract_range_admission_uses_validated_manifest(constraint, allowed):
    manifests = built_in_manifests()
    original = manifests["api"].model_dump()
    manifests["api"] = ModuleManifest.model_validate({**original, "contract_version_range": constraint})
    before = manifests["api"].model_dump()
    if allowed:
        assert ensure_module_enabled("api", "api-runtime", manifests=manifests) is None
    else:
        with pytest.raises(ModuleResolutionError) as failure:
            ensure_module_enabled("api", "api-runtime", manifests=manifests)
        assert failure.value.code == "E_MODULE_CONTRACT_INCOMPATIBLE"
        assert failure.value.detail["module_contract_version_range"] == constraint
        assert str(failure.value).startswith("E_MODULE_CONTRACT_INCOMPATIBLE: ")
    assert manifests["api"].model_dump() == before


def test_module_and_capability_admission_report_specific_missing_dependencies():
    with pytest.raises(ModuleResolutionError) as missing:
        ensure_module_enabled("absent", "developer-local")
    assert missing.value.code == "E_MODULE_NOT_FOUND"
    with pytest.raises(ModuleResolutionError) as disabled:
        ensure_module_enabled("api", "engine-only")
    assert disabled.value.code == "E_MODULE_DISABLED_BY_PROFILE"
    with pytest.raises(ModuleResolutionError) as unknown:
        ensure_capability_enabled("unknown.capability", "developer-local")
    assert unknown.value.to_payload()["code"] == "E_CAPABILITY_NOT_FOUND"
    manifests = built_in_manifests()
    manifests["api"] = ModuleManifest.model_validate({**manifests["api"].model_dump(), "required_modules": ["webhook"]})
    with pytest.raises(ModuleResolutionError) as dependency:
        ensure_capability_enabled("api.http.v1", "api-runtime", manifests=manifests)
    assert dependency.value.code == "E_MODULE_DEPENDENCY_MISSING"
    assert dependency.value.detail["missing_required_modules"] == ["webhook"]
    assert ensure_capability_enabled("api.http.v1", "api-runtime") == "api"


def test_explicit_and_context_profiles_preserve_precedence_without_ambient_settings(monkeypatch):
    monkeypatch.delenv("ORKET_MODULE_PROFILE", raising=False)

    def resolve_in_context():
        set_runtime_settings_context(user_settings={"module_profile": " API-RUNTIME "}, environment={})
        assert resolve_module_profile() == "api-runtime"
        assert resolve_module_profile(" ENGINE-ONLY ") == "engine-only"

    copy_context().run(resolve_in_context)
    assert tuple(profiles()) == ("api-runtime", "api-webhook-runtime", "developer-local", "engine-only")
