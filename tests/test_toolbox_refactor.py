import pytest
import sqlite3
from pathlib import Path
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.tools import ToolBox, FileSystemTools, CardManagementTools, VisionTools, AcademyTools, get_tool_map
from orket.core.types import CardStatus

def test_toolbox_composition(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[])
    
    assert isinstance(toolbox.fs, FileSystemTools)
    assert isinstance(toolbox.cards, CardManagementTools)
    assert toolbox.fs.workspace_root == workspace


def test_tool_map_default_parity(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[])
    tool_map = get_tool_map(toolbox)

    assert sorted(tool_map.keys()) == sorted([
        "read_file",
        "write_file",
        "list_directory",
        "image_analyze",
        "image_generate",
        "create_issue",
        "update_issue_status",
        "add_issue_comment",
        "get_issue_context",
        "nominate_card",
        "report_credits",
        "refinement_proposal",
        "request_excuse",
        "archive_eval",
        "promote_prompt",
    ])


@pytest.mark.asyncio
async def test_toolbox_execute_uses_resolved_tool_strategy(tmp_path):
    class CustomToolStrategy:
        def compose(self, toolbox):
            return {"custom_sync": lambda args, context=None: {"ok": True, "value": args["x"]}}

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    registry = DecisionNodeRegistry()
    registry.register_tool_strategy("custom", CustomToolStrategy())
    org = type("Org", (), {"process_rules": {"tool_strategy_node": "custom"}})()

    toolbox = ToolBox(
        policy={},
        workspace_root=str(workspace),
        references=[],
        organization=org,
        decision_nodes=registry,
    )

    res = await toolbox.execute("custom_sync", {"x": 7})

    assert res == {"ok": True, "value": 7}

@pytest.mark.asyncio
async def test_filesystem_tools_security(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    
    fs = FileSystemTools(workspace, [])
    
    # Read within workspace
    inside = workspace / "test.txt"
    inside.write_text("hello")
    res = await fs.read_file({"path": "test.txt"})
    assert res["ok"] is True
    assert res["content"] == "hello"
    
    # Read outside workspace (should fail)
    res = await fs.read_file({"path": str(outside)})
    assert res["ok"] is False
    assert "denied" in res["error"].lower()

@pytest.mark.asyncio
async def test_write_file_creation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fs = FileSystemTools(workspace, [])
    
    res = await fs.write_file({"path": "subdir/new.txt", "content": "data"})
    assert res["ok"] is True
    assert (workspace / "subdir" / "new.txt").read_text() == "data"

def test_vision_tools_stub(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    vision = VisionTools(workspace, [])
    
    res = vision.image_analyze({"path": "test.png"})
    assert res["ok"] is False
    assert "not implemented" in res["error"]

@pytest.mark.asyncio
async def test_academy_tools_promote_prompt(tmp_path):
    # Setup project structure
    project_root = tmp_path
    workspace = project_root / "workspace" / "default"
    workspace.mkdir(parents=True)
    prompts_dir = project_root / "prompts"
    
    academy = AcademyTools(workspace, [])
    
    res = await academy.promote_prompt({
        "seat": "lead_architect",
        "content": "You are a lead architect.",
        "model_family": "qwen"
    })
    
    assert res["ok"] is True
    expected_path = prompts_dir / "lead_architect" / "qwen.txt"
    assert expected_path.exists()
    assert expected_path.read_text() == "You are a lead architect."

@pytest.mark.asyncio
async def test_card_management_create_issue(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "test.db"
    
    cards = CardManagementTools(workspace, [], db_path=str(db_path))
    
    res = await cards.create_issue({
        "seat": "dev",
        "summary": "Fix bug",
        "priority": "High"
    }, context={"session_id": "sess-123"})
    
    assert res["ok"] is True
    assert "issue_id" in res
    
    issue = await cards.cards.get_by_id(res["issue_id"])
    assert issue.summary == "Fix bug"
    assert float(issue.priority) == 3.0


@pytest.mark.asyncio
async def test_toolbox_report_credits_uses_async_repository(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "test.db"

    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[], db_path=str(db_path))

    create_res = await toolbox.cards.create_issue(
        {"seat": "dev", "summary": "Credit test"},
        context={"session_id": "sess-credits"},
    )
    issue_id = create_res["issue_id"]

    result = await toolbox.execute("report_credits", {"amount": 2.5}, context={"issue_id": issue_id})

    assert result["ok"] is True

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT credits_spent FROM issues WHERE id = ?", (issue_id,)).fetchone()
    assert row is not None
    assert float(row[0]) == 2.5


@pytest.mark.asyncio
async def test_toolbox_request_excuse_updates_issue_status(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "test.db"

    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[], db_path=str(db_path))

    create_res = await toolbox.cards.create_issue(
        {"seat": "dev", "summary": "Excuse test"},
        context={"session_id": "sess-excuse"},
    )
    issue_id = create_res["issue_id"]

    result = await toolbox.execute(
        "request_excuse",
        {"reason": "Blocked waiting for external dependency"},
        context={"issue_id": issue_id, "role": "lead_architect"},
    )

    assert result["ok"] is True

    issue = await toolbox.cards.cards.get_by_id(issue_id)
    assert issue is not None
    assert issue.status == CardStatus.WAITING_FOR_DEVELOPER

    comments = await toolbox.cards.cards.get_comments(issue_id)
    assert any(c["content"] == "Blocked waiting for external dependency" for c in comments)


@pytest.mark.asyncio
async def test_get_issue_context_handles_issue_record_shape(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = tmp_path / "test.db"

    cards = CardManagementTools(workspace, [], db_path=str(db_path))

    create_res = await cards.create_issue(
        {"seat": "dev", "summary": "Context test"},
        context={"session_id": "sess-context"},
    )
    issue_id = create_res["issue_id"]

    await cards.add_issue_comment(
        {"comment": "First comment"},
        context={"issue_id": issue_id, "role": "dev"},
    )

    result = await cards.get_issue_context({}, context={"issue_id": issue_id})

    assert result["ok"] is True
    assert result["status"] == CardStatus.READY.value
    assert result["summary"] == "Context test"
    assert len(result["comments"]) == 1


def test_nominate_card_handles_none_context(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[])

    result = toolbox.nominate_card({"issue_id": "ISSUE-1"}, context=None)

    assert result["ok"] is True
