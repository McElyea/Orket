import json
from orket.utils import log_event
from orket.llm import call_llm


class Agent:
    """
    A single LLM-backed agent with a role and a system prompt.
    Now supports structured status signals such as:
      { "status": "waiting", "for": "tool:write_file" }
      { "status": "pending" }
      { "status": "complete" }
      { "task_complete": true }
    """

    def __init__(self, role: str, system_prompt: str):
        self.role = role
        self.system_prompt = system_prompt

    def run(self, messages: list[dict], round_num: int) -> str:
        """
        Execute one agent turn.
        messages: full conversation history so far
        round_num: current orchestrator round
        """

        # BEFORE CALL
        log_event(
            "info",
            "agent",
            "agent_before_call",
            {"agent": self.role, "round": round_num},
        )

        # Build LLM input
        llm_messages = [{"role": "system", "content": self.system_prompt}, *messages]

        # Call the model
        response = call_llm(llm_messages)
        content = response.get("content", "")

        # Attempt to parse structured status
        structured_status = None
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                if "status" in parsed or "task_complete" in parsed:
                    structured_status = parsed
        except Exception:
            pass

        # AFTER CALL
        log_event(
            "info",
            "agent",
            "agent_after_call",
            {
                "agent": self.role,
                "round": round_num,
                "content": content[:500],
                "structured_status": structured_status,
            },
        )

        return content
