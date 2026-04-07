from __future__ import annotations

from orket.exceptions import AgentConfigurationError as CoreAgentConfigurationError
from orket_extension_sdk import AgentConfigurationError as SDKAgentConfigurationError


def test_core_agent_configuration_error_is_sdk_catchable() -> None:
    """Layer: contract. Verifies SDK callers can catch host agent config failures."""
    assert issubclass(CoreAgentConfigurationError, SDKAgentConfigurationError)
