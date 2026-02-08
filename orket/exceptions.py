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
