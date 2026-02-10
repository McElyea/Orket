class OrketError(Exception):
    """Base error for the Orket Domain."""
    pass

class CardNotFound(OrketError):
    """Raised when a Rock, Epic, or Issue cannot be located."""
    pass

class ExecutionFailed(OrketError):
    """Raised when an orchestration turn fail to produce a valid result."""
    pass

class StateConflict(OrketError):
    """Raised when a status transition is invalid."""
    pass

class InfrastructureError(OrketError):
    """Wrapped technical error from persistence or filesystem."""
    pass

class ModelProviderError(OrketError):
    """Base error for LLM provider failures."""
    pass

class ModelTimeoutError(ModelProviderError):
    """Raised when the model fails to respond within the timeout period."""
    pass

class ModelConnectionError(ModelProviderError):
    """Raised when the LLM provider (e.g., Ollama) is unreachable."""
    pass

class GovernanceViolation(ExecutionFailed):
    """Raised when an architectural or organizational policy is violated."""
    pass

class ComplexityViolation(GovernanceViolation):
    """Raised when an Epic exceeds the iDesign complexity threshold."""
    pass

class CatastrophicFailure(GovernanceViolation):
    """Raised when a hard limit (like retries) is reached, requiring project shutdown."""
    pass

