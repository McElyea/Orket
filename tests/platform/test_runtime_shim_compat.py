import orket
import orket.runtime as runtime_package
import orket.runtime.execution_pipeline as execution_pipeline_module
from orket import orket as legacy
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


def test_runtime_shim_exports_match_runtime_modules():
    assert legacy.ConfigLoader is RuntimeConfigLoader
    assert legacy.ExecutionPipeline is RuntimeExecutionPipeline
    assert legacy.orchestrate is runtime_orchestrate
    assert legacy.orchestrate_card is runtime_orchestrate_card
    assert not hasattr(legacy, "orchestrate_rock")
    assert not hasattr(runtime_package, "orchestrate_rock")
    assert not hasattr(execution_pipeline_module, "orchestrate_rock")
    assert not hasattr(orket, "orchestrate_rock")


def test_runtime_shims_do_not_bless_orchestrate_rock_in_public_export_lists():
    assert "orchestrate_rock" not in runtime_package.__all__
    assert "orchestrate_rock" not in legacy.__all__
    assert "orchestrate_rock" not in orket.__all__
