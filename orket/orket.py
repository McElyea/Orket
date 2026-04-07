"""Compatibility shim for legacy imports.

Primary runtime modules now live under `orket.runtime`.
"""

import warnings

from orket.runtime import (
    ConfigLoader,
    ExecutionPipeline,
    orchestrate,
    orchestrate_card,
)

__all__ = [
    "ConfigLoader",
    "ExecutionPipeline",
    "orchestrate",
    "orchestrate_card",
]

for _exported_name in __all__:
    warnings.warn(
        f"orket.orket.{_exported_name} is deprecated; import from orket.runtime directly.",
        DeprecationWarning,
        stacklevel=2,
    )
