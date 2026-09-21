"""Pure projections of supplied diagnostic records, never completion or replay verdicts."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime
from typing import Any


def record_session_id(record: dict[str, Any]) -> str:
    data = record.get("data", {})
    if isinstance(data, dict):
        runtime_event = data.get("runtime_event", {})
        if isinstance(runtime_event, dict):
            return str(runtime_event.get("session_id") or "")
        return str(data.get("session_id") or "")
    return ""


def _total_tokens(value: Any) -> int:
    raw = value.get("total_tokens") if isinstance(value, dict) else value
    try:
        parsed = int(raw or 0)
    except (TypeError, ValueError):
        parsed = 0
    return parsed if parsed > 0 else 0


def _deduplicated(records: Iterable[dict[str, Any]], *, replay: bool) -> Iterator[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        data = record.get("data") or {}
        signature = (record.get("timestamp"), record.get("event"), str(data.get("turn_trace_id") or ""),
                     str(record.get("role") or ""), str(data.get("issue_id") or ""))
        if replay:
            signature += (str(data.get("turn_index") or ""),)
        if signature not in seen:
            seen.add(signature)
            yield record


def _turns(records: Iterable[dict[str, Any]], session_id: str, *, replay: bool,
           role_filter: str = "") -> Iterator[dict[str, Any]]:
    models: dict[str, str] = {}
    for record in _deduplicated(records, replay=replay):
        if record_session_id(record) != session_id:
            continue
        data = record.get("data", {})
        if not isinstance(data, dict):
            continue
        runtime = data.get("runtime_event", {})
        runtime = runtime if isinstance(runtime, dict) else {}
        trace = str(runtime.get("turn_trace_id") or data.get("turn_trace_id") or "").strip()
        event = str(record.get("event") or "")
        if event == "turn_start":
            model = str(runtime.get("selected_model") or data.get("selected_model") or "").strip()
            if trace and model:
                models[trace] = model
            continue
        if event != "turn_complete":
            continue
        role = str(record.get("role") or runtime.get("role") or data.get("role") or "unknown").strip().lower()
        if role_filter and role != role_filter:
            continue
        try:
            turn_index = int(runtime.get("turn_index") or data.get("turn_index") or 0)
        except (TypeError, ValueError):
            turn_index = 0
        yield {
            "session_id": session_id,
            "issue_id": str(runtime.get("issue_id") or data.get("issue_id") or "").strip() or None,
            "turn_index": turn_index,
            "role": role,
            "turn_trace_id": trace or None,
            # A whitespace model remains empty after normalization; preserve the historical fallback order.
            "model_input": models.get(trace) or runtime.get("selected_model") or data.get("selected_model"),
            "timestamp": str(record.get("timestamp") or ""),
            "tokens_input": (runtime.get("tokens"), data.get("tokens"), data.get("total_tokens")),
        }


def token_summary(records: Iterable[dict[str, Any]], session_id: str) -> dict[str, Any]:
    turns: list[dict[str, Any]] = []
    roles: dict[str, int] = {}
    models: dict[str, int] = {}
    role_models: dict[str, int] = {}
    for turn in _turns(records, session_id, replay=False):
        model = str(turn["model_input"] or "unknown").strip().lower()
        role = turn["role"]
        runtime_tokens, data_tokens, total_tokens = turn.pop("tokens_input")
        total = _total_tokens(runtime_tokens) or _total_tokens(data_tokens) or _total_tokens(total_tokens)
        turn["tokens_total"] = total
        turns.append({key: turn[key] for key in ("turn_trace_id", "issue_id", "turn_index", "role", "tokens_total")}
                     | {"model": model})
        roles[role] = roles.get(role, 0) + total
        models[model] = models.get(model, 0) + total
        key = f"{role}:{model}"
        role_models[key] = role_models.get(key, 0) + total
    turns.sort(key=lambda item: (item["turn_index"], str(item["issue_id"] or ""), str(item["role"])))
    by_role_model = []
    for key, total in sorted(role_models.items()):
        role, model = key.split(":", 1)
        by_role_model.append({"role": role, "model": model, "tokens_total": total})
    return {
        "session_id": session_id, "total_tokens": sum(roles.values()), "turn_count": len(turns),
        "by_role": [{"role": key, "tokens_total": value} for key, value in sorted(roles.items())],
        "by_model": [{"model": key, "tokens_total": value} for key, value in sorted(models.items())],
        "by_role_model": by_role_model, "turns": turns,
    }


def replay_turns(records: Iterable[dict[str, Any]], session_id: str, role: str | None) -> list[dict[str, Any]]:
    role_filter = str(role or "").strip().lower()
    turns = []
    for turn in _turns(records, session_id, replay=True, role_filter=role_filter):
        turn.pop("tokens_input")
        turn["selected_model"] = str(turn.pop("model_input") or "").strip() or None
        turns.append(turn)
    turns.sort(key=lambda item: (item["turn_index"], str(item["issue_id"] or ""), str(item["role"]), item["timestamp"]))
    return turns


def handoff_edges(records: Iterable[dict[str, Any]], session_id: str,
                  index_by_id: Mapping[str, int]) -> list[dict[str, Any]]:
    turns: list[tuple[int, str, str]] = []
    for record in records:
        if record_session_id(record) != session_id or str(record.get("event") or "").strip() != "turn_complete":
            continue
        data = record.get("data", {})
        data = data if isinstance(data, dict) else {}
        runtime = data.get("runtime_event", {})
        runtime = runtime if isinstance(runtime, dict) else {}
        issue_id = str(runtime.get("issue_id") or data.get("issue_id") or "").strip()
        if not issue_id or issue_id not in index_by_id:
            continue
        try:
            turn_index = int(runtime.get("turn_index") or data.get("turn_index") or 0)
        except (TypeError, ValueError):
            turn_index = 0
        turns.append((turn_index, str(record.get("timestamp") or ""), issue_id))
    turns.sort(key=lambda row: (row[0], row[1]))
    edges = []
    previous_issue: str | None = None
    for turn_index, timestamp, issue_id in turns:
        if previous_issue and previous_issue != issue_id:
            edges.append({"source": previous_issue, "target": issue_id, "kind": "handoff",
                          "source_event": "turn_complete", "timestamp": timestamp, "turn_index": turn_index})
        previous_issue = issue_id
    return edges


def log_page(records: Iterable[dict[str, Any]], *, session_id: str | None, event: str | None, role: str | None,
             start_dt: datetime | None, end_dt: datetime | None, limit: int, offset: int) -> dict[str, Any]:
    filtered = []
    for record in records:
        if session_id and record_session_id(record) != session_id:
            continue
        if event and str(record.get("event") or "") != event:
            continue
        if role and str(record.get("role") or "") != role:
            continue
        try:
            timestamp = datetime.fromisoformat(str(record.get("timestamp") or ""))
        except ValueError:
            timestamp = None
        if start_dt and (timestamp is None or timestamp < start_dt):
            continue
        if end_dt and (timestamp is None or timestamp > end_dt):
            continue
        filtered.append(record)
    filtered.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    page = filtered[offset:offset + limit]
    return {"items": page, "count": len(page), "total": len(filtered), "limit": limit, "offset": offset}
