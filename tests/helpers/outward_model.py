from __future__ import annotations

from types import SimpleNamespace


class FakeOutwardModelClient:
    def __init__(self, *, tool: str = "write_file", args: dict[str, object] | None = None) -> None:
        self.tool = tool
        self.args = args or {"path": "model-output.txt", "content": "model output"}
        self.messages: list[dict[str, str]] = []
        self.runtime_context: dict[str, object] = {}
        self.closed = False

    async def complete(self, messages, runtime_context=None):
        self.messages = list(messages)
        self.runtime_context = dict(runtime_context or {})
        return SimpleNamespace(
            content="",
            raw={
                "tool_calls": [{"type": "function", "function": {"name": self.tool, "arguments": self.args}}],
                "provider_name": "fake-provider",
                "provider_backend": "fake-provider",
                "model": "fake-model",
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                "latency_ms": 23,
                "orket_session_id": "fake-session",
                "openai_compat": {"choices": [{"finish_reason": "tool_calls"}]},
            },
        )

    async def close(self) -> None:
        self.closed = True


def patch_outward_model_client(monkeypatch, *, tool: str = "write_file", args: dict[str, object] | None = None):
    import orket.application.services.outward_model_tool_call_service as model_service_module

    client = FakeOutwardModelClient(tool=tool, args=args)
    monkeypatch.setattr(model_service_module, "create_configured_model_client", lambda: client)
    return client
