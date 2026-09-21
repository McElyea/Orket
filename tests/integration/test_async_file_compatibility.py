"""Native pre-loop compatibility and platform-specific root admission contracts."""
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools


@pytest.mark.integration
@pytest.mark.parametrize("content", ["native café", {"values": ["native", 42]}])
def test_file_tool_preloop_round_trip_and_read_only_references(tmp_path, content):
    reference = tmp_path / "reference"
    reference.mkdir()
    reference_file = reference / "retained.txt"
    reference_file.write_text("reference", encoding="utf-8")
    references = [reference]
    tools = AsyncFileTools(tmp_path / "workspace", references)
    assert tools.create_directory_sync("nested") == str(tmp_path / "workspace/nested")
    assert tools.write_file_sync("nested/file.txt", content) == str(tmp_path / "workspace/nested/file.txt")
    expected = content if isinstance(content, str) else json.dumps(content, indent=2)
    assert tools.read_file_sync("nested/file.txt") == expected
    assert tools.list_directory_sync("nested") == ["file.txt"]
    assert tools.read_file_sync(str(reference_file)) == "reference"
    with pytest.raises(PermissionError, match="Write access denied"):
        tools.write_file_sync(str(reference_file), "denied")
    assert reference_file.read_text(encoding="utf-8") == "reference"
    assert tools.references is references


@pytest.mark.contract
@pytest.mark.parametrize("field", ["workspace", "reference"])
def test_file_tool_binds_relative_roots_or_refuses_drive_relative_roots(tmp_path, monkeypatch, field):
    monkeypatch.chdir(tmp_path)
    path = Path(tmp_path.drive + "relative")
    tools = AsyncFileTools(path if field == "workspace" else tmp_path, [path] if field == "reference" else [])
    if tmp_path.drive:
        with pytest.raises(ValueError, match="E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
            tools.capture()
    else:
        captured = tools.capture()
        assert (captured.workspace_root if field == "workspace" else captured.references[0]) == tmp_path / "relative"
