"""Explicit close-capable pipeline port for API dispatch contract tests."""
from types import SimpleNamespace


class SandboxLogPipeline:
    def __init__(self, **methods):
        self.sandbox_orchestrator = SimpleNamespace(**methods)
        self.closed = False

    async def close(self):
        self.closed = True
