import json
import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

CONSOLE_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
CURRENT_LEVEL = CONSOLE_LEVELS.get("debug", 10)  # adjust as needed


def _ts():
    return datetime.utcnow().isoformat() + "Z"


def log_event(level: str, component: str, event: str, payload: dict):
    """
    Central log router.
    - Writes JSONL to logs/all.jsonl
    - Prints formatted line to console (respecting level)
    """
    record = {
        "ts": _ts(),
        "level": level,
        "component": component,
        "event": event,
        "payload": payload,
    }

    # JSONL sink
    path = os.path.join(LOG_DIR, "all.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Console (level-filtered)
    if CONSOLE_LEVELS.get(level, 100) >= CURRENT_LEVEL:
        print(format_log_record(record))


def format_log_record(record: dict) -> str:
    """
    Human-readable console formatter.
    Example:
      [2026-02-01T21:26:55Z] [INFO] [architect] agent_output: round=1 ...
    """
    ts = record["ts"]
    level = record["level"].upper()
    component = record["component"]
    event = record["event"]
    payload = record.get("payload", {})

    round_no = payload.get("round")
    content = payload.get("content")

    if isinstance(content, str) and len(content) > 160:
        content = content[:157] + "..."

    parts = [f"[{ts}]", f"[{level}]", f"[{component}]", event]

    if round_no is not None:
        parts.append(f"round={round_no}")

    if content:
        parts.append(f"content={json.dumps(content, ensure_ascii=False)}")

    return " ".join(parts)