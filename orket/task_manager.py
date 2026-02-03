import uuid
import datetime
import json
from orket.utils import log_event


class TaskManager:
    """
    Manages task lifecycle, agent rotation, and completion detection.
    Now supports structured completion signals and internal round tracking.
    """

    def __init__(self, max_rounds: int = 50):
        self.task_id = str(uuid.uuid4())
        self.round = 0
        self.max_rounds = max_rounds
        self.agents = []

    # ------------------------------------------------------------
    # Agent rotation
    # ------------------------------------------------------------

    def set_agents(self, agent_names: list[str]):
        self.agents = agent_names

    def next_agent(self, agent_names: list[str]) -> str:
        if not agent_names:
            raise ValueError("No agents available for rotation")
        index = self.round % len(agent_names)
        return agent_names[index]

    # ------------------------------------------------------------
    # Completion detection
    # ------------------------------------------------------------

    def is_complete(self, content: str) -> bool:
        """
        Structured completion > fallback heuristics > safety stop.
        """

        # 1. Structured JSON completion
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                if data.get("task_complete") is True:
                    return True
                if data.get("status") == "complete":
                    return True
        except Exception:
            pass

        # 2. Fallback heuristics
        lowered = content.lower()
        if "task complete" in lowered:
            return True
        if "done." in lowered:
            return True
        if "finished" in lowered:
            return True

        # 3. Safety stop
        if self.round >= self.max_rounds:
            log_event(
                "warn", "orchestrator", "max_rounds_reached", {"round": self.round}
            )
            return True

        return False

    # ------------------------------------------------------------
    # Round tracking
    # ------------------------------------------------------------

    def increment_round(self):
        self.round += 1
