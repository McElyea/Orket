import pytest
from pathlib import Path
from orket.tools import ToolBox, FileSystemTools, CardManagementTools

def test_toolbox_composition(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    
    toolbox = ToolBox(policy={}, workspace_root=str(workspace), references=[])
    
    assert isinstance(toolbox.fs, FileSystemTools)
    assert isinstance(toolbox.cards, CardManagementTools)
    assert toolbox.fs.workspace_root == workspace

def test_filesystem_tools_security(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    
    fs = FileSystemTools(workspace, [])
    
    # Read within workspace
    inside = workspace / "test.txt"
    inside.write_text("hello")
    res = fs.read_file({"path": "test.txt"})
    assert res["ok"] is True
    assert res["content"] == "hello"
    
    # Read outside workspace (should fail)
    res = fs.read_file({"path": str(outside)})
    assert res["ok"] is False
    assert "denied" in res["error"].lower()

def test_write_file_creation(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    fs = FileSystemTools(workspace, [])
    
    res = fs.write_file({"path": "subdir/new.txt", "content": "data"})
    assert res["ok"] is True
    assert (workspace / "subdir" / "new.txt").read_text() == "data"
