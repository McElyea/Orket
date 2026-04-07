class OrketSDKError(Exception):
    """Base error for public Orket extension SDK exceptions."""


class AgentConfigurationError(OrketSDKError):
    """Raised when a host agent cannot load required governance configuration."""


__all__ = ["AgentConfigurationError", "OrketSDKError"]
