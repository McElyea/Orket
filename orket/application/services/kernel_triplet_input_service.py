"""Detach and canonicalize one complete triplet before local state publication."""

from typing import Any

from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.core.contracts.kernel_triplet import KernelTripletInputs
from orket.kernel.v1.canonical import canonical_json_bytes


def capture_kernel_triplet(
    body: dict[str, Any], links: dict[str, Any], manifest: dict[str, Any]
) -> KernelTripletInputs:
    captured = capture_kernel_request({"body": body, "links": links, "manifest": manifest})
    return KernelTripletInputs(*(canonical_json_bytes(captured[key]) for key in ("body", "links", "manifest")))
