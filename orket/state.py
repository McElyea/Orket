# orket/state.py
import asyncio
from typing import Dict, List, Any

class GlobalState:
    """Global singleton for cross-module coordination."""
    def __init__(self):
        self.interventions: Dict[str, Dict[str, str]] = {}
        self.event_queue = asyncio.Queue()
        self.active_websockets: List[Any] = []
        self.active_tasks: Dict[str, asyncio.Task] = {}

runtime_state = GlobalState()
