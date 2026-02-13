"""Compatibility shim: records moved to `orket.core.domain.records`."""

from orket.core.domain.records import IssueRecord, CardRecord

__all__ = ["IssueRecord", "CardRecord"]
