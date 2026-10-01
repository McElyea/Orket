"""Explicit logging admission for selected constructor-bypassing unit/contract fixtures."""
from orket.adapters.observability.logging_context import prepare_logging
from orket.core.contracts.logging_inputs import LoggingInputs


async def prepared_fixture_owner(owner_type, root):
    """Keep the fixture's partial graph while supplying one genuinely prepared log selection."""
    prepared = await prepare_logging(LoggingInputs(root))
    owner = owner_type.__new__(owner_type)
    owner.logging_context = prepared
    return owner
