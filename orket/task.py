import os
import json
import uuid
from datetime import datetime


class Task:
    """
    Represents a single orchestrated task.
    Stores:
      - request
      - round count
      - agent messages
      - per-task memory directory
    """

    def __init__(self, request: str, memory_dir: str):
        self.id = str(uuid.uuid4())
        self.request = request
        self.round = 0
        self.messages = []
        self.memory_dir = memory_dir

    def increment_round(self):
        self.round += 1

    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "ts": datetime.utcnow().isoformat() + "Z"
        })

    def get_messages(self):
        return self.messages

    def save_memory(self):
        if not self.memory_dir:
            return

        os.makedirs(self.memory_dir, exist_ok=True)

        path = os.path.join(self.memory_dir, f"{self.id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "id": self.id,
                "request": self.request,
                "rounds": self.round,
                "messages": self.messages,
            }, f, indent=2, ensure_ascii=False)
