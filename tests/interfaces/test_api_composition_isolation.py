from __future__ import annotations

import importlib
from pathlib import Path


def test_api_import_does_not_construct_mutable_runtime_singletons() -> None:
    """Layer: contract. Verifies mutable API runtime owners stay lazy even though the app-scoped context exists."""
    module = importlib.import_module("orket.interfaces.api")
    module = importlib.reload(module)

    assert module.stream_bus is None
    assert module.interaction_manager is None
    assert module.extension_manager is None
    assert module.app.state.api_runtime_context.project_root == module._project_root()
    assert module.app.state.api_runtime_context.engine is module.engine


def test_create_api_app_rebuilds_runtime_objects_for_distinct_project_roots(tmp_path: Path) -> None:
    """Layer: integration. Verifies repeated API app creation replaces the app-scoped runtime context instead of reusing hidden module-global owners."""
    module = importlib.import_module("orket.interfaces.api")
    root_a = (tmp_path / "workspace_a").resolve()
    root_b = (tmp_path / "workspace_b").resolve()

    app_a = module.create_api_app(project_root=root_a)
    context_a = app_a.state.api_runtime_context
    interaction_a = module._get_interaction_manager()
    stream_a = module._get_stream_bus()
    extension_a = module._get_extension_manager()

    app_b = module.create_api_app(project_root=root_b)
    context_b = app_b.state.api_runtime_context
    interaction_b = module._get_interaction_manager()
    stream_b = module._get_stream_bus()
    extension_b = module._get_extension_manager()

    assert app_a is app_b
    assert context_a is not context_b
    assert id(interaction_a) != id(interaction_b)
    assert id(stream_a) != id(stream_b)
    assert id(extension_a) != id(extension_b)
    assert root_b == module._project_root()
    assert interaction_b.project_root == root_b
    assert extension_b.project_root == root_b
    assert context_b.engine is module.engine
    assert context_b.stream_bus is stream_b
    assert context_b.interaction_manager is interaction_b
    assert context_b.extension_manager is extension_b


def test_engine_compatibility_alias_syncs_into_app_state_context(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. Verifies legacy module-level engine monkeypatches are compatibility aliases over the app-scoped context."""
    module = importlib.import_module("orket.interfaces.api")
    app = module.create_api_app(project_root=tmp_path)
    replacement_engine = type("ReplacementEngine", (), {})()

    monkeypatch.setattr(module, "engine", replacement_engine)

    assert module._get_engine() is replacement_engine
    assert app.state.api_runtime_context.engine is replacement_engine
