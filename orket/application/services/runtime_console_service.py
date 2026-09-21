"""Own blocking console input without confusing normal EOF with cancellation."""
from orket.adapters.execution.owned_io import run_owned_thread


async def read_console_line(prompt: str) -> str | None:
    reader = input

    def read():
        try:
            return reader(prompt)
        except EOFError:
            return None

    return await run_owned_thread(read, label="runtime-console-input")
