# orket/prelude.py
from orket.utils import log_event
from orket.llm import call_llm


def run_prelude(architect_prompt: str, task: str) -> str:
    """
    Optional pre-stage where the architect reflects on the task
    before the main Session begins.
    """
    messages = [
        {"role": "system", "content": architect_prompt},
        {"role": "user", "content": task},
    ]

    log_event(
        "info",
        "prelude",
        "prelude_start",
        {"task_preview": task[:200]},
    )

    response = call_llm(messages)
    content = response.get("content", "")

    log_event(
        "info",
        "prelude",
        "prelude_end",
        {"content_preview": content[:200]},
    )

    return content
