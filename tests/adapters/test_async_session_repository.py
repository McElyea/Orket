from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_repositories import AsyncSessionRepository

pytestmark = pytest.mark.integration


def _session_payload() -> dict[str, str]:
    return {
        "type": "unit",
        "name": "session",
        "department": "core",
        "task_input": "do work",
    }


@pytest.mark.asyncio
async def test_session_repository_reinitializes_after_db_file_recreated(tmp_path: Path) -> None:
    """Layer: integration. Verifies session schema creation is tied to the DB, not the Python object."""
    db_path = tmp_path / "sessions.sqlite3"
    repo = AsyncSessionRepository(db_path)
    await repo.start_session("session-before-delete", _session_payload())

    db_path.unlink()

    await repo.start_session("session-after-delete", _session_payload())

    loaded = await repo.get_session("session-after-delete")
    assert loaded is not None
    assert loaded["id"] == "session-after-delete"
