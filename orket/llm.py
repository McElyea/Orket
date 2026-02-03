import json
import requests
from orket.utils import log_event

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "llama3.1:8b"


def call_llm(messages: list[dict]) -> dict:
    """
    Stable, modern Ollama chat API call.
    Works on Windows. No subprocess. No escape codes.
    """

    log_event(
        "info",
        "llm",
        "llm_call_start",
        {"message_count": len(messages), "model": MODEL_NAME},
    )

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        content = data.get("message", {}).get("content", "")

        log_event(
            "info",
            "llm",
            "llm_call_end",
            {"content_preview": content[:200]},
        )

        return {"content": content}

    except Exception as e:
        log_event(
            "error",
            "llm",
            "llm_exception",
            {"error": str(e)},
        )
        return {"content": f"[LLM ERROR] {e}"}
