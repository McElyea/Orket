"""Layer: integration. Fixture-model turns persist actual prompt provenance files.

The declared model fixture supplies read/write proposals. The tool fixture performs
them through the existing file owner; this is not live-provider acceptance.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATH = "agent_output/source.txt"
_WRITE_PATH = "agent_output/observation.txt"
_WRITE_CONTENT = "Observed retained source content.\n"


class _ReadProposal:
    def __init__(self):
        self.messages = None

    async def complete(self, messages):
        self.messages = messages
        return SimpleNamespace(
            content="\n".join(json.dumps(call) for call in (
                {"tool": "read_file", "args": {"path": _READ_PATH}},
                {"tool": "write_file", "args": {"path": _WRITE_PATH, "content": _WRITE_CONTENT}},
            )),
            raw={"fixture": "message-compaction-artifacts"},
        )


class _OwnedFileTools:
    def __init__(self, workspace: Path):
        self.files = AsyncFileTools(workspace)
        self.observed = []

    async def execute(self, tool_name, args, context=None):
        if tool_name == "read_file":
            assert args == {"path": _READ_PATH}
            content = await self.files.read_file(args["path"])
            self.observed.append(content)
            return {"ok": True, "content": content}
        assert tool_name == "write_file" and args == {"path": _WRITE_PATH, "content": _WRITE_CONTENT}
        return {"ok": True, "path": await self.files.write_file(args["path"], args["content"])}


def _context(compact: bool, metadata: dict, layers: dict) -> dict:
    return {
        "session_id": "message-artifacts", "turn_index": 0, "issue_id": "ISSUE-ARTIFACT",
        "role": "reviewer", "roles": ["reviewer"], "current_status": "in_progress",
        "selected_model": "declared-file-proposal-fixture", "required_action_tools": ["read_file", "write_file"],
        "required_statuses": [], "required_read_paths": [_READ_PATH], "required_write_paths": [_WRITE_PATH],
        "history": [], "stage_gate_mode": "auto",
        "compact_turn_packet_enabled": compact, "prompt_metadata": metadata, "prompt_layers": layers,
    }


@pytest.mark.parametrize("compact", [False, True], ids=["legacy-prompt", "compact-packet"])
async def test_compaction_outputs_survive_turn_artifact_publication(tmp_path: Path, compact: bool):
    files = AsyncFileTools(tmp_path)
    await files.write_file(_READ_PATH, "Retained source content.\n")
    metadata = {"prompt_id": "artifact-fixture", "prompt_checksum": "original-checksum"}
    layers = {"fixture_layer": {"name": "retained"}}
    context = _context(compact, metadata, layers)
    model, toolbox = _ReadProposal(), _OwnedFileTools(tmp_path)
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path), workspace=tmp_path, utc_now=artifact_test_utc_now)
    issue = IssueConfig(id="ISSUE-ARTIFACT", summary="Read admitted source", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(id="reviewer", name="reviewer", description="Review source", tools=["read_file", "write_file"])

    result = await executor.execute_turn(
        issue=issue, role=role, model_client=model, toolbox=toolbox, context=context, system_prompt="Review the source.",
    )

    assert result.success is True
    assert toolbox.observed == ["Retained source content.\n"]
    assert await files.read_file(_WRITE_PATH) == _WRITE_CONTENT
    assert "Retained source content." in "\n".join(message["content"] for message in model.messages)
    output = tmp_path / "observability/message-artifacts/issue-artifact/000_reviewer"
    published_layers = json.loads(await asyncio.to_thread((output / "prompt_layers.json").read_text, encoding="utf-8"))
    checkpoint = json.loads(await asyncio.to_thread((output / "checkpoint.json").read_text, encoding="utf-8"))
    assert context["prompt_metadata"] is metadata and context["prompt_layers"] is layers
    assert published_layers == layers
    assert checkpoint["prompt_metadata"] == metadata
    assert published_layers["fixture_layer"] == {"name": "retained"}
    assert checkpoint["prompt_metadata"]["prompt_id"] == "artifact-fixture"
    if compact:
        expected_checksum = hashlib.sha256(model.messages[0]["content"].encode("utf-8")).hexdigest()[:16]
        assert checkpoint["prompt_metadata"]["prompt_checksum"] == expected_checksum
        assert checkpoint["prompt_metadata"]["prompt_packet_compacted"] is True
        assert checkpoint["prompt_metadata"]["prompt_packet_version"] == "compact_turn_packet_v1"
        assert published_layers["packet_compaction"]["compacted_message_count"] == 2
        assert published_layers["packet_compaction"]["source_message_count"] > 2
    else:
        assert checkpoint["prompt_metadata"]["prompt_checksum"] == "original-checksum"
        assert "prompt_packet_compacted" not in metadata and "packet_compaction" not in layers
    assert await files.read_file(_READ_PATH) == "Retained source content.\n"
