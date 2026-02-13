from orket import orket as legacy
from orket.runtime import (
    ConfigLoader as RuntimeConfigLoader,
    ExecutionPipeline as RuntimeExecutionPipeline,
    orchestrate as runtime_orchestrate,
    orchestrate_card as runtime_orchestrate_card,
    orchestrate_rock as runtime_orchestrate_rock,
)


def test_runtime_shim_exports_match_runtime_modules():
    assert legacy.ConfigLoader is RuntimeConfigLoader
    assert legacy.ExecutionPipeline is RuntimeExecutionPipeline
    assert legacy.orchestrate is runtime_orchestrate
    assert legacy.orchestrate_card is runtime_orchestrate_card
    assert legacy.orchestrate_rock is runtime_orchestrate_rock

