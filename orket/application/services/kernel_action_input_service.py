"""Transfer borrowed JSON into values owned by one kernel publication invocation."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from orket_extension_sdk import FrozenJson


def capture_kernel_request(request: dict[str, Any]) -> dict[str, Any]:
    return FrozenJson.freeze(request).thaw()


def capture_kernel_publication_inputs(
    request: dict[str, Any], response: dict[str, Any], ledger_items: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    captured = FrozenJson.freeze([request, response, list(ledger_items)])
    owned_request, owned_response, owned_ledger = captured.thaw()
    return owned_request, owned_response, owned_ledger
