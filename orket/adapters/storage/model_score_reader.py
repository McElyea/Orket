"""Read-only score observation; invoke this worker through owned thread I/O."""
from __future__ import annotations

import hashlib
import json
from math import isfinite
from pathlib import Path

from orket.core.contracts.model_selection import ModelScoreObservation


def read_model_scores(report_path: str) -> ModelScoreObservation:
    path = Path(report_path).resolve()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ModelScoreObservation(str(path), "missing", error="Configured score report does not exist.")
    except OSError as exc:
        return ModelScoreObservation(str(path), "unavailable", error=f"{type(exc).__name__}: {exc}")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError) as exc:
        return ModelScoreObservation(str(path), "invalid", digest, f"{type(exc).__name__}: invalid JSON")
    rows = payload.get("model_compliance") if isinstance(payload, dict) else None
    if not isinstance(rows, dict):
        return ModelScoreObservation(str(path), "invalid", digest, "model_compliance must be an object.")
    scores, invalid = [], 0
    for model, detail in rows.items():
        value = detail.get("compliance_score") if isinstance(detail, dict) else None
        try:
            score = float(value)
        except (TypeError, ValueError):
            invalid += 1
            continue
        if not isfinite(score):
            invalid += 1
            continue
        scores.append((str(model), score))
    return ModelScoreObservation(str(path), "partial" if invalid else "observed", digest,
                                 f"{invalid} invalid score rows." if invalid else "", tuple(sorted(scores)))
