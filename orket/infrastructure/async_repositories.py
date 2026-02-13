"""Compatibility shim: moved to `orket.adapters.storage.async_repositories`."""

from orket.adapters.storage.async_repositories import AsyncSessionRepository, AsyncSnapshotRepository

__all__ = ["AsyncSessionRepository", "AsyncSnapshotRepository"]

