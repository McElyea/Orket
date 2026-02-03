# orket/__init__.py
"""
Orket package initializer.

This module exposes the public API surface for:
- loading Venues
- constructing the dispatcher
- constructing the filesystem policy
- running the orchestrator

No side effects occur at import time.
"""

from .orket import orchestrate
from venues.venue_loader import load_venue
from .filesystem import FilesystemPolicy

__all__ = [
    "orchestrate",
    "load_venue",
    "FilesystemPolicy",
]

__version__ = "0.2.0"