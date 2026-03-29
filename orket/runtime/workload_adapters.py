from __future__ import annotations

# Compatibility shim: keep only the raw cards workload-contract builder here.
# Governed workload authority must resolve through
# orket.application.services.control_plane_workload_catalog.resolve_control_plane_workload.
from orket.application.services.control_plane_workload_catalog import (
    CARDS_CONTROL_PLANE_WORKLOAD_ID,
    build_cards_workload_contract,
)

__all__ = [
    "CARDS_CONTROL_PLANE_WORKLOAD_ID",
    "build_cards_workload_contract",
]
