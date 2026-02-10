import json
import os
from datetime import datetime, UTC

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

CONSOLE_LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
CURRENT_LEVEL = CONSOLE_LEVELS.get("debug", 10)  # adjust as needed


from orket.naming import sanitize_name

def get_eos_sprint(date_obj: datetime = None) -> str:
    """Calculates EOS Sprint based on 1-week sprints (Mon-Fri) and 13-sprint quarters."""
    if date_obj is None: date_obj = datetime.now()
    
    # Simple calculation based on your provided info: 
    # Feb 6, 2026 is end of Q1 S6.
    # Base date: Feb 2, 2026 was start of Q1 S6.
    base_date = datetime(2026, 2, 2)
    base_q, base_s = 1, 6
    
    delta_weeks = (date_obj - base_date).days // 7
    total_sprints = base_s + delta_weeks
    
    q = base_q + (total_sprints - 1) // 13
    s = (total_sprints - 1) % 13 + 1
    
    return f"Q{q} S{s}"

def _ts():
    return datetime.now(UTC).isoformat()


from orket.logging import log_event
