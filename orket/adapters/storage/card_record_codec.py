from __future__ import annotations

import json
from typing import Any

side_effecting = False


def deserialize_card_row(row: dict[str, Any]) -> dict[str, Any]:
    for field in ["verification_json", "metrics_json", "params_json", "depends_on_json"]:
        target = field.replace("_json", "")
        if row.get(field):
            try:
                row[target] = json.loads(row[field])
            except json.JSONDecodeError:
                row[target] = [] if target == "depends_on" else {}
        else:
            row[target] = [] if target == "depends_on" else {}
    # Completion authority never inherits the legacy support-field recovery defaults.
    raw_context = row.get("completion_context_json")
    row["completion_context"] = json.loads(raw_context) if raw_context is not None else None
    return row
