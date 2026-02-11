import pytest

from orket.schema import CardStatus
from orket.tools import CardManagementTools


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
