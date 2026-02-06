from pathlib import Path
import json
from orket import orchestrate
from orket.llm import LocalModelProvider


class DummyProvider(LocalModelProvider):
    def __init__(self):
        super().__init__(model="dummy")

    def invoke(self, prompt: str):
        # Just record that we were called
        self.last_prompt = prompt
        from dataclasses import dataclass

        @dataclass
        class DummyResponse:
            content: str
            raw: dict

        return DummyResponse(content="dummy response", raw={"prompt": prompt})


def test_model_invocation(monkeypatch, tmp_path):
    # Patch LocalModelProvider to our dummy
    dummy = DummyProvider()

    def _dummy_init(self, model: str, temperature: float = 0.2, seed=None):
        # Ignore args, reuse dummy instance
        pass

    def _dummy_invoke(self, prompt: str):
        return dummy.invoke(prompt)

    monkeypatch.setattr(LocalModelProvider, "__init__", _dummy_init)
    monkeypatch.setattr(LocalModelProvider, "invoke", _dummy_invoke)

    flow_path = Path("model/flow/standard.json")
    task = {"description": "Test that the model is invoked."}
    workspace = tmp_path / "session"

    result = orchestrate(flow_path=flow_path, task=task, workspace=workspace, use_prelude=False)

    assert "transcript" in result
    assert len(result["transcript"]) > 0
    assert hasattr(dummy, "last_prompt"), "Model provider was never invoked"
    assert "Test that the model is invoked." in dummy.last_prompt
    