class OrketSDKError(Exception):
    """Base error for public Orket extension SDK exceptions."""


class AgentConfigurationError(OrketSDKError):
    """Raised when a host agent cannot load required governance configuration."""


class AgentProtocolError(OrketSDKError):
    """Raised when the governed-agent host/child protocol fails closed."""


class AgentInvocationCancelled(OrketSDKError):
    """Raised when the host cancels an active governed-agent invocation."""


class AgentBrokerDisconnected(OrketSDKError):
    """Raised when the host broker is no longer available for governed calls."""


__all__ = [
    "AgentBrokerDisconnected",
    "AgentConfigurationError",
    "AgentInvocationCancelled",
    "AgentProtocolError",
    "OrketSDKError",
]
