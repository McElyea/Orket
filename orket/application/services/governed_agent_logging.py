"""Bind prepared logging at the standalone governed CLI application boundary."""
from orket.adapters.observability.logging_context import bind_logging, prepare_logging, select_logging_inputs


async def run_with_agent_logging(root, environment, operation):
    prepared = await prepare_logging(select_logging_inputs(root, environment))
    with bind_logging(prepared):
        return await operation()
