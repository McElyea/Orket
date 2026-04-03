from __future__ import annotations

import asyncio
import json
from pathlib import Path

from scripts.observability.emit_run_evidence_graph import main
from tests.runtime.run_evidence_graph_test_support import (
    GENERATED_AT,
    seed_complete_primary_lineage_sqlite,
)


# Layer: integration
def test_emit_run_evidence_graph_writes_canonical_artifact_family(tmp_path: Path) -> None:
    _, _, db_path, session_id, run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    mermaid_path = tmp_path / "runs" / session_id / "run_evidence_graph.mmd"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == run_id
    assert payload["graph_result"] == "complete"
    assert payload["selected_views"] == [
        "full_lineage",
        "failure_path",
        "resource_authority_path",
        "closure_path",
    ]
    assert mermaid_path.exists()
    assert html_path.exists()
    assert 'subgraph view_full_lineage["Full Lineage | ' in mermaid_path.read_text(encoding="utf-8")
    assert "Failure Path" in html_path.read_text(encoding="utf-8")


# Layer: integration
def test_emit_run_evidence_graph_returns_blocked_when_selected_run_has_no_primary_lineage(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / ".orket" / "durable" / "db" / "control_plane_records.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = "sess-graph-blocked"
    run_id = f"kernel-action-run:{session_id}:trace-missing"
    (tmp_path / "runs" / session_id).mkdir(parents=True, exist_ok=True)

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--session-id",
            session_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 1
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["graph_result"] == "blocked"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert "run_record_missing" in html_path.read_text(encoding="utf-8")


# Layer: integration
def test_emit_run_evidence_graph_accepts_authority_and_decision_views(tmp_path: Path) -> None:
    _, _, db_path, session_id, run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))

    exit_code = main(
        [
            "--run-id",
            run_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
            "--view",
            "decision",
            "--view",
            "authority",
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    html_path = tmp_path / "runs" / session_id / "run_evidence_graph.html"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["selected_views"] == ["authority", "decision"]
    html = html_path.read_text(encoding="utf-8")
    assert "Authority" in html
    assert "Decision" in html


# Layer: integration
def test_emit_run_evidence_graph_resolves_control_plane_run_id_from_session_summary(tmp_path: Path) -> None:
    _, _, db_path, session_id, control_plane_run_id = asyncio.run(seed_complete_primary_lineage_sqlite(tmp_path=tmp_path))
    run_summary_path = tmp_path / "runs" / session_id / "run_summary.json"
    payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
    payload["run_id"] = session_id
    payload["control_plane"] = {"run_id": control_plane_run_id}
    run_summary_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    exit_code = main(
        [
            "--run-id",
            session_id,
            "--workspace-root",
            str(tmp_path),
            "--control-plane-db",
            str(db_path),
            "--generation-timestamp",
            GENERATED_AT,
        ]
    )

    assert exit_code == 0
    json_path = tmp_path / "runs" / session_id / "run_evidence_graph.json"
    graph_payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert graph_payload["run_id"] == control_plane_run_id
    assert graph_payload["graph_result"] in {"complete", "degraded"}
