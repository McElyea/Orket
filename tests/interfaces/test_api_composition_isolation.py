from __future__ import annotations

import importlib
from pathlib import Path


def test_api_import_does_not_construct_mutable_runtime_singletons() -> None:
    module = importlib.import_module("orket.interfaces.api")
    module = importlib.reload(module)

    assert module.stream_bus is None
    assert module.interaction_manager is None
    assert module.extension_manager is None


def test_create_api_app_rebuilds_runtime_objects_for_distinct_project_roots(tmp_path: Path) -> None:
    module = importlib.import_module("orket.interfaces.api")
    root_a = (tmp_path / "workspace_a").resolve()
    root_b = (tmp_path / "workspace_b").resolve()

    app_a = module.create_api_app(project_root=root_a)
    interaction_a = module._get_interaction_manager()
    stream_a = module._get_stream_bus()
    extension_a = module._get_extension_manager()

    app_b = module.create_api_app(project_root=root_b)
    interaction_b = module._get_interaction_manager()
    stream_b = module._get_stream_bus()
    extension_b = module._get_extension_manager()

    assert app_a is app_b
    assert id(interaction_a) != id(interaction_b)
    assert id(stream_a) != id(stream_b)
    assert id(extension_a) != id(extension_b)
    assert root_b == module._project_root()
    assert interaction_b.project_root == root_b
    assert extension_b.project_root == root_b
