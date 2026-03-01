from __future__ import annotations


class GiteaAdapterError(RuntimeError):
    pass


class GiteaAdapterRateLimitError(GiteaAdapterError):
    pass


class GiteaAdapterAuthError(GiteaAdapterError):
    pass


class GiteaAdapterConflictError(GiteaAdapterError):
    pass


class GiteaAdapterTimeoutError(GiteaAdapterError):
    pass


class GiteaAdapterNetworkError(GiteaAdapterError):
    pass
