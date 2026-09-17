"""Explicit transaction ownership for related ControlPlane persistence ports."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from orket.core.contracts.pending_gate_repository import PendingGateRepository
from orket.core.contracts.repositories import ControlPlaneExecutionRepository, ControlPlaneRecordRepository


@dataclass(frozen=True)
class ControlPlaneTransaction:
    execution: ControlPlaneExecutionRepository
    records: ControlPlaneRecordRepository
    pending_gates: PendingGateRepository


ControlPlaneTransactionFactory = Callable[[], AbstractAsyncContextManager[ControlPlaneTransaction]]
