import pytest

from orket.schema import CardStatus
from orket.tools import CardManagementTools


class SpyToolGate:
    def __init__(self, violation: str | None = None):
        self.violation = violation
        self.calls = []

    def validate(self, tool_name, args, context, roles):
        self.calls.append(
            {
                "tool_name": tool_name,
                "args": args,
                "context": context,
                "roles": roles,
            }
        )
        return self.violation


@pytest.mark.asyncio
async def test_update_issue_status_enforces_transition_rules(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "state_machine.db"

    cards = CardManagementTools(workspace, [], db_path=str(db_path))
    await cards.cards.save(
        {
            "id": "ISSUE-STATE-1",
            "session_id": "sess-1",
            "build_id": "build-1",
            "seat": "dev",
            "summary": "State test",
            "type": "issue",
            "priority": 2.0,
            "status": CardStatus.READY,
        }
    )

    result = await cards.update_issue_status(
        {"status": "done"},
        context={"issue_id": "ISSUE-STATE-1", "role": "developer"},
    )
    assert result["ok"] is False
    assert "invalid transition" in result["error"].lower()


@pytest.mark.asyncio
async def test_update_issue_status_requires_wait_reason_for_blocked(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "state_machine_wait.db"

    cards = CardManagementTools(workspace, [], db_path=str(db_path))
    await cards.cards.save(
        {
            "id": "ISSUE-STATE-2",
            "session_id": "sess-2",
            "build_id": "build-2",
            "seat": "dev",
            "summary": "Wait reason test",
            "type": "issue",
            "priority": 2.0,
            "status": CardStatus.IN_PROGRESS,
        }
    )

    result = await cards.update_issue_status(
        {"status": "blocked"},
        context={"issue_id": "ISSUE-STATE-2", "role": "developer"},
    )
    assert result["ok"] is False
    assert "wait_reason" in result["error"].lower()


@pytest.mark.asyncio
async def test_update_issue_status_valid_transition_succeeds(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "state_machine_valid.db"

    cards = CardManagementTools(workspace, [], db_path=str(db_path))
    await cards.cards.save(
        {
            "id": "ISSUE-STATE-3",
            "session_id": "sess-3",
            "build_id": "build-3",
            "seat": "dev",
            "summary": "Valid transition test",
            "type": "issue",
            "priority": 2.0,
            "status": CardStatus.READY,
        }
    )

    result = await cards.update_issue_status(
        {"status": "in_progress"},
        context={"issue_id": "ISSUE-STATE-3", "role": "developer"},
    )
    assert result["ok"] is True
    assert result["status"] == "in_progress"


@pytest.mark.asyncio
async def test_update_issue_status_delegates_to_tool_gate(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "state_machine_gate.db"
    gate = SpyToolGate()

    cards = CardManagementTools(workspace, [], db_path=str(db_path), tool_gate=gate)
    await cards.cards.save(
        {
            "id": "ISSUE-STATE-4",
            "session_id": "sess-4",
            "build_id": "build-4",
            "seat": "dev",
            "summary": "Gate delegation test",
            "type": "issue",
            "priority": 2.0,
            "status": CardStatus.READY,
        }
    )

    result = await cards.update_issue_status(
        {"status": "in_progress"},
        context={"issue_id": "ISSUE-STATE-4", "roles": ["developer"]},
    )

    assert result["ok"] is True
    assert len(gate.calls) == 1
    assert gate.calls[0]["tool_name"] == "update_issue_status"
    assert gate.calls[0]["context"]["current_status"] == "ready"


@pytest.mark.asyncio
async def test_update_issue_status_blocks_when_tool_gate_rejects(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "state_machine_gate_block.db"
    gate = SpyToolGate(violation="blocked by policy")

    cards = CardManagementTools(workspace, [], db_path=str(db_path), tool_gate=gate)
    await cards.cards.save(
        {
            "id": "ISSUE-STATE-5",
            "session_id": "sess-5",
            "build_id": "build-5",
            "seat": "dev",
            "summary": "Gate block test",
            "type": "issue",
            "priority": 2.0,
            "status": CardStatus.READY,
        }
    )

    result = await cards.update_issue_status(
        {"status": "in_progress"},
        context={"issue_id": "ISSUE-STATE-5", "roles": ["developer"]},
    )

    assert result["ok"] is False
    assert result["error"] == "blocked by policy"

    issue = await cards.cards.get_by_id("ISSUE-STATE-5")
    assert issue.status == CardStatus.READY

