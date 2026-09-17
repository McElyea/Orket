from __future__ import annotations

import os

from orket.core.contracts.provider_runtime import provider_from_environment


def configured_provider(*keys: str) -> str:
    """Resolve explicit provider settings, ignoring blank values, then the default."""
    return provider_from_environment(dict(os.environ), *keys)
