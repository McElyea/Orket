"""Integration: MessageBuilder admits only governed workspace-relative read tokens."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiofiles
import pytest

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.application.workflows.turn_path_resolver import PathResolver
from orket.schema import IssueConfig, RoleConfig

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _issue() -> IssueConfig:
    return IssueConfig(id="READ-1", summary="Read admitted inputs", status="in_progress")


def _role() -> RoleConfig:
    return RoleConfig(
        id="reviewer",
        summary="reviewer",
        description="Review admitted files",
        prompt="Review the required inputs.",
        tools=["read_file", "add_issue_comment"],
    )


def _context(paths: list[str], *, compact: bool = True) -> dict[str, object]:
    return {
        "session_id": "read-admission",
        "turn_index": 1,
        "issue_id": "READ-1",
        "role": "reviewer",
        "current_status": "in_progress",
        "required_action_tools": ["read_file", "add_issue_comment"],
        "required_statuses": ["code_review"],
        "required_read_paths": paths,
        "required_write_paths": [],
        "history": [],
        "compact_turn_packet_enabled": compact,
    }


def _render(messages: list[dict[str, str]]) -> str:
    return "\n\n".join(message["content"] for message in messages)


def _trap_content_open(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    calls: list[object] = []

    def forbidden_open(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("invalid required-read token reached native file-content open")

    monkeypatch.setattr(aiofiles, "open", forbidden_open)
    return calls


@pytest.mark.parametrize("compact", [False, True])
async def test_relative_existing_and_missing_reads_preserve_classification_and_content(
    tmp_path: Path,
    compact: bool,
) -> None:
    workspace = tmp_path / "workspace"
    existing = workspace / "inputs" / "accepted.txt"
    expected_bytes = b"accepted line one\r\naccepted line two\n"
    await asyncio.to_thread(existing.parent.mkdir, parents=True)
    await asyncio.to_thread(existing.write_bytes, expected_bytes)
    before_bytes = await asyncio.to_thread(existing.read_bytes)

    messages = await MessageBuilder(workspace).prepare_messages(
        issue=_issue(),
        role=_role(),
        context=_context(["inputs/accepted.txt", "inputs/missing.txt"], compact=compact),
    )
    rendered = _render(messages)

    assert "Path: inputs/accepted.txt" in rendered
    assert "accepted line one\naccepted line two" in rendered
    assert "inputs/missing.txt" in rendered
    assert ("Missing Inputs:" in rendered) is compact
    assert ("Missing Input Preflight Notice:" in rendered) is (not compact)
    assert rendered.index("Path: inputs/accepted.txt") < rendered.index("inputs/missing.txt", rendered.index("Path:"))
    assert before_bytes == expected_bytes
    assert await asyncio.to_thread(existing.read_bytes) == expected_bytes


@pytest.mark.parametrize(
    ("case", "detail"),
    [
        ("traversal", "read_file:path_traversal"),
        ("absolute_outside", "read_file:absolute_path"),
        ("absolute_inside", "read_file:absolute_path"),
    ],
)
async def test_invalid_required_read_token_fails_before_content_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    detail: str,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    inside = workspace / "inside.txt"
    await asyncio.to_thread(workspace.mkdir)
    await asyncio.to_thread(outside.write_text, "outside secret", encoding="utf-8")
    await asyncio.to_thread(inside.write_text, "inside secret", encoding="utf-8")
    outside_bytes = await asyncio.to_thread(outside.read_bytes)
    inside_bytes = await asyncio.to_thread(inside.read_bytes)
    outside_absolute, inside_absolute = await asyncio.gather(
        asyncio.to_thread(outside.resolve), asyncio.to_thread(inside.resolve)
    )
    token = {
        "traversal": "../outside.txt",
        "absolute_outside": str(outside_absolute),
        "absolute_inside": str(inside_absolute),
    }[case]

    observed_detail = await asyncio.to_thread(
        PathResolver.workspace_constraint_violation,
        tool_name="read_file",
        args={"path": token},
        workspace=workspace,
    )
    assert observed_detail == detail
    open_calls = _trap_content_open(monkeypatch)

    with pytest.raises(ValueError) as raised:
        await MessageBuilder(workspace).prepare_messages(
            issue=_issue(), role=_role(), context=_context([token])
        )

    assert str(raised.value) == f"E_WORKSPACE_CONSTRAINT:{detail}"
    assert open_calls == []
    assert await asyncio.to_thread(outside.read_bytes) == outside_bytes
    assert await asyncio.to_thread(inside.read_bytes) == inside_bytes


async def test_escaping_symlink_fails_before_content_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "reference-like-outside"
    link = workspace / "escape"
    await asyncio.to_thread(workspace.mkdir)
    await asyncio.to_thread(outside.mkdir)
    await asyncio.to_thread((outside / "secret.txt").write_text, "outside secret", encoding="utf-8")
    expected_bytes = await asyncio.to_thread((outside / "secret.txt").read_bytes)
    try:
        await asyncio.to_thread(link.symlink_to, outside, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlink unavailable on this Windows host: {exc}")

    token = "escape/secret.txt"
    detail = "read_file:path_escape"
    observed_detail = await asyncio.to_thread(
        PathResolver.workspace_constraint_violation,
        tool_name="read_file",
        args={"path": token},
        workspace=workspace,
    )
    assert observed_detail == detail
    open_calls = _trap_content_open(monkeypatch)

    with pytest.raises(ValueError) as raised:
        await MessageBuilder(workspace).prepare_messages(
            issue=_issue(), role=_role(), context=_context([token])
        )

    assert str(raised.value) == f"E_WORKSPACE_CONSTRAINT:{detail}"
    assert open_calls == []
    assert await asyncio.to_thread((outside / "secret.txt").read_bytes) == expected_bytes
