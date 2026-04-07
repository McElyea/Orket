from __future__ import annotations

from orket.session import Session, TranscriptTurn


def test_session_add_turn_validates_transcript_turn() -> None:
    """Layer: contract. Verifies session transcript turns are schema-validated replay records."""
    session = Session.start("sess-1", "issue", "Issue 1", "core", "do work")

    session.add_turn(
        {
            "role": "agent",
            "summary": "wrote file",
            "turn_index": 1,
            "tool_calls": [{"tool": "write_file", "args": {"path": "a.txt"}}],
        }
    )

    assert isinstance(session.transcript[0], TranscriptTurn)
    assert session.to_dict()["transcript"][0]["schema_version"] == "1.0.0"
    assert session.to_dict()["transcript"][0]["tool_calls"][0]["tool"] == "write_file"


def test_session_transcript_migrates_legacy_content_dict() -> None:
    """Layer: contract. Verifies old untyped transcript rows are parsed defensively."""
    session = Session(
        id="sess-1",
        type="issue",
        name="Issue 1",
        department="core",
        transcript=[{"role": "agent", "content": "legacy summary"}],
    )

    assert session.transcript[0].summary == "legacy summary"
    assert session.transcript[0].turn_index == 0
    assert session.to_dict()["transcript"][0]["summary"] == "legacy summary"
