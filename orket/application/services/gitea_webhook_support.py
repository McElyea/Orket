from __future__ import annotations

from typing import Any


def _response_error(*, action: str, response: Any) -> str | None:
    status_code = int(getattr(response, "status_code", 0) or 0)
    if 200 <= status_code < 300:
        return None
    detail = f"{action} failed with status {status_code}"
    response_text = str(getattr(response, "text", "") or "").strip()
    if response_text:
        detail = f"{detail}: {response_text}"
    return detail


def _webhook_event_id(payload: dict[str, Any]) -> str:
    for key in ("event_id", "delivery_id", "x_gitea_delivery", "X-Gitea-Delivery"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""
