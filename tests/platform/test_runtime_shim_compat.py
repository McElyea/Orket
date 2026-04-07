import importlib
import warnings

import orket
import orket.runtime as runtime_package
import orket.runtime.execution_pipeline as execution_pipeline_module
from orket.runtime import (
    ConfigLoader as RuntimeConfigLoader,
)
from orket.runtime import (
    ExecutionPipeline as RuntimeExecutionPipeline,
)
from orket.runtime import (
    orchestrate as runtime_orchestrate,
)
from orket.runtime import (
    orchestrate_card as runtime_orchestrate_card,
)


def _legacy_module():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return importlib.import_module("orket.orket")


def test_runtime_shim_exports_match_runtime_modules():
    legacy = _legacy_module()

    assert legacy.ConfigLoader is RuntimeConfigLoader
    assert legacy.ExecutionPipeline is RuntimeExecutionPipeline
    assert legacy.orchestrate is runtime_orchestrate
    assert legacy.orchestrate_card is runtime_orchestrate_card
    assert not hasattr(legacy, "orchestrate_rock")
    assert not hasattr(runtime_package, "orchestrate_rock")
    assert not hasattr(execution_pipeline_module, "orchestrate_rock")
    assert not hasattr(orket, "orchestrate_rock")


def test_runtime_shims_do_not_bless_orchestrate_rock_in_public_export_lists():
    legacy = _legacy_module()

    assert "orchestrate_rock" not in runtime_package.__all__
    assert "orchestrate_rock" not in legacy.__all__
    assert "orchestrate_rock" not in orket.__all__


def test_legacy_runtime_shim_emits_deprecation_warnings():
    legacy = _legacy_module()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        importlib.reload(legacy)

    messages = [str(entry.message) for entry in captured]
    assert any("orket.orket.ConfigLoader is deprecated" in message for message in messages)
    assert any("orket.orket.ExecutionPipeline is deprecated" in message for message in messages)
