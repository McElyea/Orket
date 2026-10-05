"""Integration: actual native writes retain the submitted UTF-8 line endings."""
import asyncio
import json

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.tools.families.filesystem import FileSystemTools
from tests.helpers.outward_authorization import approve, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("content", ["café\nnext\n", "a\r\nb\r\n", "a\rb\nlast\r\n", {"value": [1, 2]}])
@pytest.mark.parametrize("layer", ["adapter", "family"])
async def test_native_text_write_preserves_exact_serialized_bytes(tmp_path, content, layer):
    expected = content if isinstance(content, str) else json.dumps(content, indent=2)
    if layer == "adapter":
        await AsyncFileTools(tmp_path).write_file("exact.txt", content)
    else:
        result = await FileSystemTools(tmp_path, []).write_file({"path": "exact.txt", "content": content})
        assert result["ok"]
    assert await asyncio.to_thread((tmp_path / "exact.txt").read_bytes) == expected.encode("utf-8")


@pytest.mark.parametrize("content", ["café\nnext\n", "a\r\nb\r\n"])
async def test_approved_bound_write_preserves_exact_bytes(tmp_path, boundary, content):
    database, inputs, calls = boundary
    calls[:] = [{"tool": "write_file", "args": {"path": "exact.txt", "content": content}}]
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal = await submit_sequence(client, calls)
        response = await approve(client, proposal)
        assert response.status_code == 200, response.text
        effect, _journal = await effect_snapshot(database, proposal)
        assert effect.state == "published" and effect.receipt["result"]["ok"]
        assert await asyncio.to_thread((tmp_path / "exact.txt").read_bytes) == content.encode("utf-8")
