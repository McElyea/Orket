"""Native evidence publication with controlled model responses, not real inference."""
from __future__ import annotations

import asyncio
import hashlib
import json
from types import SimpleNamespace

import pytest

from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_model_tool_call_service import (
    OutwardModelToolCallError,
    OutwardModelToolCallService,
)
from orket.exceptions import ModelProviderError
from tests.helpers.evidence_ownership import model_evidence_directory, model_evidence_inputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
CALL = {"tool": "write_file", "args": {"path": "proposal-only.txt", "content": "proposed"}}


class ControlledClient:
    def __init__(self, response=None, failure=None):
        self.response, self.failure = response, failure
        self.calls = []
        self.closed = False

    async def complete(self, messages, runtime_context=None):
        self.calls.append((messages, runtime_context))
        if self.failure is not None:
            raise self.failure
        return self.response

    async def close(self):
        self.closed = True


def _service(root, client):
    return OutwardModelToolCallService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
                                     workspace_root=root, model_client_factory=lambda: client)


async def _invoke(root, client):
    inputs = model_evidence_inputs(root)
    return await _service(root, client).produce_governed_tool_call(
        run=inputs["run"], expected_tool="write_file", governed_tools={"write_file"},
        evidence_scope=inputs["evidence_scope"],
    )


async def _read_bundle(root):
    directory = model_evidence_directory(root)
    bundle = {}
    for stem in ("model_invocation", "model_prompt_redacted", "model_response_redacted", "proposal_extraction"):
        material = await asyncio.to_thread((directory / f"{stem}_turn_1.json").read_bytes)
        bundle[stem] = json.loads(material)
        assert bundle[stem]["run_id"] == "native-run"
    assert not await asyncio.to_thread((root / "proposal-only.txt").exists)
    return bundle


@pytest.mark.parametrize("expected,governed,message", [
    (" ", {"write_file"}, "expected governed tool is required"),
    ("write_file", {" "}, "run has no governed tool family"),
    ("write_file", {"read_file"}, "not in governed tool family"),
    ("unregistered", {"unregistered"}, "not registered"),
])
async def test_invalid_tool_family_refuses_before_model_or_evidence(tmp_path, expected, governed, message):
    created = []

    def construct():
        created.append(True)
        raise AssertionError("invalid admission constructed a model")

    service = OutwardModelToolCallService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY,
                                        workspace_root=tmp_path, model_client_factory=construct)
    with pytest.raises(OutwardModelToolCallError, match=message):
        await service.produce_governed_tool_call(run=model_evidence_inputs(tmp_path)["run"],
                                               expected_tool=expected, governed_tools=governed)
    assert created == [] and not await asyncio.to_thread((tmp_path / "workspace").exists)


@pytest.mark.parametrize("envelope", ["direct", "tool_call", "governed_tool_call", "tool_calls", "fenced", "native"])
async def test_supported_responses_publish_matching_extraction_and_close(tmp_path, envelope):
    payload = CALL if envelope in {"direct", "fenced", "native"} else {
        envelope: [CALL] if envelope == "tool_calls" else CALL,
    }
    content = json.dumps(payload)
    raw = {"provider_name": "controlled-fixture"}
    if envelope == "fenced":
        content = "```json\n" + content + "\n```"
    elif envelope == "native":
        content = "not used when native calls exist"
        raw["tool_calls"] = [None, {"function": {"name": "write_file", "arguments": json.dumps(CALL["args"])}}]
    response = SimpleNamespace(content=content, raw=raw)
    client = ControlledClient(response)
    result = await _invoke(tmp_path, client)
    assert result.tool_call == CALL and result.response is response
    assert client.closed and len(client.calls) == 1
    context = client.calls[0][1]
    assert context["native_tool_choice"] == "required" and context["required_action_tools"] == ["write_file"]
    assert context["native_tools"][0]["function"]["name"] == "write_file"
    bundle = await _read_bundle(tmp_path)
    assert bundle["model_invocation"]["result"] == "tool_call_extracted"
    assert bundle["model_invocation"]["error_type"] is None
    assert bundle["proposal_extraction"]["extracted_tool_name"] == "write_file"
    for ref, digest in (("model_invocation_ref", "model_invocation_sha256"),
                        ("model_prompt_ref", "model_prompt_redacted_sha256"),
                        ("model_response_ref", "model_response_redacted_sha256"),
                        ("proposal_extraction_ref", "proposal_extraction_sha256")):
        material = await asyncio.to_thread((tmp_path / result.model_invocation[ref]).read_bytes)
        assert hashlib.sha256(material).hexdigest() == result.model_invocation[digest]


@pytest.mark.parametrize("content,raw,message", [
    ("", [], "did not include a tool call"),
    ("```\nnot JSON\n```", {}, "content is not valid JSON"),
    ("[]", {}, "must be an object"),
    ('{"tool_call": []}', {}, "must be an object"),
    ('{"args": {}}', {}, "missing a tool name"),
    ('{"tool":"write_file","args":"not JSON"}', {}, "arguments are not valid JSON"),
    ('{"tool":"write_file","args":[]}', {}, "arguments must be an object"),
    ("", {"tool_calls": [{"function": {"name": "", "arguments": {}}}]}, "missing a tool name"),
])
async def test_invalid_response_retains_diagnostic_evidence_and_cause(tmp_path, content, raw, message):
    client = ControlledClient(SimpleNamespace(content=content, raw=raw))
    with pytest.raises(OutwardModelToolCallError, match="failed: OutwardModelToolCallError") as failure:
        await _invoke(tmp_path, client)
    assert isinstance(failure.value.__cause__, OutwardModelToolCallError)
    assert message in str(failure.value.__cause__)
    assert client.closed and len(client.calls) == 1
    bundle = await _read_bundle(tmp_path)
    assert bundle["model_invocation"]["result"] == "invalid_tool_call"
    assert bundle["model_invocation"]["error_type"] == "OutwardModelToolCallError"
    assert bundle["model_response_redacted"]["extracted_tool_call_redacted"] is None
    assert bundle["proposal_extraction"]["extracted_tool_name"] is None


@pytest.mark.parametrize("error_type", [ModelProviderError, RuntimeError, ValueError])
async def test_provider_failure_retains_native_failure_evidence_and_original_cause(tmp_path, error_type):
    original = error_type("controlled provider failure")
    client = ControlledClient(failure=original)
    with pytest.raises(OutwardModelToolCallError, match="failed: " + error_type.__name__) as failure:
        await _invoke(tmp_path, client)
    assert failure.value.__cause__ is original and client.closed and len(client.calls) == 1
    bundle = await _read_bundle(tmp_path)
    assert bundle["model_invocation"]["result"] == "provider_error"
    assert bundle["model_invocation"]["error_type"] == error_type.__name__
    assert bundle["model_invocation"]["tool_name"] is None
    assert bundle["proposal_extraction"]["extracted_tool_name"] is None
