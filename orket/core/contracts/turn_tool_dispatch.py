"""A dispatch admission is evidence of uncertainty, never evidence of an effect."""
from orket.core.contracts.control_plane_models import StepRecord

DISPATCH_STARTED = "dispatch_started"
TURN_TOOL_DISPATCH_CONTRACT = "turn_tool.dispatch_intent.v1"


def is_unresolved_tool_dispatch(step: StepRecord) -> bool:
    return step.closure_classification == DISPATCH_STARTED or step.observed_result_classification == DISPATCH_STARTED
