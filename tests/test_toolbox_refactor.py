import pytest
from pathlib import Path
from orket.tools import ToolBox, FileSystemTools, CardManagementTools, VisionTools, AcademyTools

def test_toolbox_composition(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[])
    
    assert isinstance(toolbox.fs, FileSystemTools)
    assert isinstance(toolbox.cards, CardManagementTools)
    assert toolbox.fs.workspace_root == workspace

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
