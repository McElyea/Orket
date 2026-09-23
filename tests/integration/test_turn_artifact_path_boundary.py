"""Layer: integration. Real artifact-path boundary counterexamples.

The unsafe cases exercise real synchronous filesystem writes, but their candidate
destinations are checked to remain inside pytest's disposable ``tmp_path`` before
any write. They demonstrate lexical workspace escape only; symlink and hostile
native containment are outside this probe.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from tests.helpers.turn_artifacts import artifact_destination

pytestmark = pytest.mark.integration
_FILENAME = "path-boundary.txt"
_CONTENT = "physical artifact path observation"


def _record(record_property, **values) -> None:
    record_property("artifact_path_observation", json.dumps(values, sort_keys=True))


def _unsafe_inputs(kind: str, tmp_path: Path) -> tuple[str, str]:
    if kind == "absolute-session":
        return str((tmp_path / "absolute-session-escape").resolve()), "artifact-issue"
    return "..", "../traversal-session-issue"


@pytest.mark.parametrize("kind", ["absolute-session", "traversal-session-issue"])
def test_artifact_writer_refuses_lexical_workspace_escape(tmp_path, record_property, kind):
    workspace = tmp_path / "owned-workspace"
    writer = TurnArtifactWriter(workspace)
    session_id, issue_id = _unsafe_inputs(kind, tmp_path)
    escaped = tmp_path / ("absolute-session-escape/artifact-issue" if kind == "absolute-session"
                          else "traversal-session-issue") / "001_reviewer" / _FILENAME
    try:
        destination = artifact_destination(writer,
            session_id=session_id, issue_id=issue_id, role_name="reviewer", turn_index=1,
        )
        directory = destination.output_dir
    except ValueError as error:
        assert str(error).startswith("E_TURN_ARTIFACT_PATH_COMPONENT:")
        assert escaped.resolve().is_relative_to(tmp_path.resolve())
        assert not escaped.exists() and not workspace.exists()
        _record(record_property, case=kind, result="refused", refusal_stage="path-construction",
                error_type=type(error).__name__, actual_path=str(escaped.resolve()), physical_file_exists=False)
        return

    resolved_root = tmp_path.resolve()
    resolved_workspace = workspace.resolve()
    resolved_target = (directory / _FILENAME).resolve()
    if not resolved_target.is_relative_to(resolved_root):
        pytest.skip("Current sanitizer changes the absolute temporary root on this case-sensitive host")
    assert not resolved_target.is_relative_to(resolved_workspace)

    error = None
    try:
        writer.write_turn_artifact(
            destination=destination,
            filename=_FILENAME,
            content=_CONTENT,
        )
    except ValueError as caught:
        error = caught

    exists = resolved_target.is_file()
    physical_bytes = resolved_target.read_bytes() if exists else None
    _record(
        record_property,
        case=kind,
        result="refused" if error is not None else "escaped_write",
        error_type=None if error is None else type(error).__name__,
        requested_session=session_id,
        requested_issue=issue_id,
        workspace=str(resolved_workspace),
        actual_path=str(resolved_target),
        inside_tmp_path=resolved_target.is_relative_to(resolved_root),
        outside_owned_workspace=not resolved_target.is_relative_to(resolved_workspace),
        physical_file_exists=exists,
        physical_bytes=None if physical_bytes is None else physical_bytes.decode("utf-8"),
    )
    if error is not None:
        assert not exists
        return
    assert physical_bytes == _CONTENT.encode("utf-8")
    pytest.fail("TurnArtifactWriter admitted a lexical path outside its owned workspace")


@pytest.mark.parametrize(
    ("session_id", "issue_id", "role_name", "turn_index", "relative"),
    [
        ("Session A", "Issue A", "Reviewer", 1,
         Path("observability/session_a/issue_a/001_reviewer") / _FILENAME),
        ("blank-role", "turn-zero", "", 0,
         Path("observability/blank-role/turn-zero/000_unknown") / _FILENAME),
    ],
    ids=["normal", "blank-role-turn-zero"],
)
def test_artifact_writer_preserves_benign_path_behavior(
    tmp_path, record_property, session_id, issue_id, role_name, turn_index, relative,
):
    workspace = tmp_path / "owned-workspace"
    writer = TurnArtifactWriter(workspace)
    writer.write_turn_artifact(
        destination=artifact_destination(writer, session_id=session_id, issue_id=issue_id,
                                          role_name=role_name, turn_index=turn_index),
        filename=_FILENAME,
        content=_CONTENT,
    )
    target = workspace / relative
    resolved_target = target.resolve()
    assert resolved_target.is_relative_to(workspace.resolve())
    assert resolved_target.is_relative_to(tmp_path.resolve())
    assert target.read_bytes() == _CONTENT.encode("utf-8")
    _record(
        record_property,
        case="blank-role-turn-zero" if not role_name else "normal",
        result="written",
        workspace=str(workspace.resolve()),
        actual_path=str(resolved_target),
        relative_path=relative.as_posix(),
        physical_file_exists=True,
        physical_bytes=_CONTENT,
    )
