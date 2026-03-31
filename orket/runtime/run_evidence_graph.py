from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles

RUN_EVIDENCE_GRAPH_SCHEMA_VERSION = "1.0"
_GRAPH_RESULTS = {"complete", "degraded", "blocked"}
RUN_EVIDENCE_GRAPH_VIEW_ORDER = (
    "full_lineage",
    "failure_path",
    "resource_authority_path",
    "closure_path",
)
_NODE_FAMILIES = {
    "run",
    "attempt",
    "step",
    "reservation",
    "lease",
    "resource",
    "observation",
    "checkpoint",
    "checkpoint_acceptance",
    "effect",
    "recovery_decision",
    "reconciliation",
    "operator_action",
    "final_truth",
}
_EDGE_FAMILIES = {
    "run_to_attempt",
    "attempt_to_step",
    "attempt_to_checkpoint",
    "reservation_to_lease_promotion",
    "lease_to_resource_authority",
    "step_to_checkpoint",
    "checkpoint_to_checkpoint_acceptance",
    "step_to_effect",
    "attempt_to_recovery_decision",
    "step_to_observation",
    "observation_to_effect",
    "observation_to_resource",
    "observation_to_final_truth",
    "reconciliation_to_final_truth",
    "operator_action_to_affected_transition",
    "operator_action_to_affected_resource",
    "final_truth_to_run",
}
_AUTHORITY_LEVELS = {"primary", "supplemental"}
_SOURCE_STATUSES = {"present", "missing", "contradictory", "unused"}
_PROJECTION_FRAMING = {
    "artifact_family": "run_evidence_graph",
    "scope": "single_selected_run",
    "lineage_rule": "primary_lineage_with_bounded_supplemental_annotation",
}


def build_run_evidence_graph_payload(
    *,
    run_id: str,
    generation_timestamp: str,
    graph_result: str,
    selected_views: list[str],
    source_summaries: list[dict[str, Any]] | None = None,
    issues: list[dict[str, Any]] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canonical_payload = {
        "run_evidence_graph_schema_version": RUN_EVIDENCE_GRAPH_SCHEMA_VERSION,
        "run_id": str(run_id).strip(),
        "projection_only": True,
        "graph_result": str(graph_result).strip(),
        "projection_framing": dict(_PROJECTION_FRAMING),
        "generation_timestamp": str(generation_timestamp).strip(),
        "selected_views": _canonicalize_selected_views(selected_views),
        "source_summaries": _canonicalize_source_summaries(source_summaries or []),
        "issues": _canonicalize_issues(issues or []),
        "nodes": _canonicalize_nodes(nodes or []),
        "edges": _canonicalize_edges(edges or []),
    }
    canonical_payload["node_count"] = len(canonical_payload["nodes"])
    canonical_payload["edge_count"] = len(canonical_payload["edges"])
    validate_run_evidence_graph_payload(canonical_payload)
    return canonical_payload


def build_blocked_run_evidence_graph_payload(
    *,
    run_id: str,
    generation_timestamp: str,
    selected_views: list[str],
    issues: list[dict[str, Any]],
    source_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return build_run_evidence_graph_payload(
        run_id=run_id,
        generation_timestamp=generation_timestamp,
        graph_result="blocked",
        selected_views=selected_views,
        source_summaries=source_summaries or [],
        issues=issues,
        nodes=[],
        edges=[],
    )


async def write_run_evidence_graph_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    validate_run_evidence_graph_payload(payload)
    graph_path = Path(root) / "runs" / str(session_id).strip() / "run_evidence_graph.json"
    await asyncio.to_thread(graph_path.parent.mkdir, parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    async with aiofiles.open(graph_path, mode="w", encoding="utf-8") as handle:
        await handle.write(content)
    return graph_path


def validate_run_evidence_graph_payload(payload: dict[str, Any]) -> None:
    if str(payload.get("run_evidence_graph_schema_version") or "").strip() != RUN_EVIDENCE_GRAPH_SCHEMA_VERSION:
        raise ValueError("run_evidence_graph_schema_version_invalid")
    if not str(payload.get("run_id") or "").strip():
        raise ValueError("run_evidence_graph_run_id_required")
    if payload.get("projection_only") is not True:
        raise ValueError("run_evidence_graph_projection_only_invalid")

    graph_result = str(payload.get("graph_result") or "").strip()
    if graph_result not in _GRAPH_RESULTS:
        raise ValueError("run_evidence_graph_result_invalid")

    projection_framing = payload.get("projection_framing")
    if not isinstance(projection_framing, dict):
        raise ValueError("run_evidence_graph_projection_framing_invalid")
    for field_name, expected_value in _PROJECTION_FRAMING.items():
        if str(projection_framing.get(field_name) or "").strip() != expected_value:
            raise ValueError(f"run_evidence_graph_projection_framing_{field_name}_invalid")

    if not str(payload.get("generation_timestamp") or "").strip():
        raise ValueError("run_evidence_graph_generation_timestamp_required")

    selected_views = payload.get("selected_views")
    if not isinstance(selected_views, list) or not selected_views:
        raise ValueError("run_evidence_graph_selected_views_invalid")
    if selected_views != _canonicalize_selected_views(selected_views):
        raise ValueError("run_evidence_graph_selected_views_not_canonical")

    source_summaries = payload.get("source_summaries")
    if not isinstance(source_summaries, list):
        raise ValueError("run_evidence_graph_source_summaries_invalid")
    if source_summaries != _canonicalize_source_summaries(source_summaries):
        raise ValueError("run_evidence_graph_source_summaries_not_canonical")
    source_ids = _validate_source_summaries(source_summaries)

    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise ValueError("run_evidence_graph_issues_invalid")
    if issues != _canonicalize_issues(issues):
        raise ValueError("run_evidence_graph_issues_not_canonical")
    _validate_issues(issues=issues, source_ids=source_ids)

    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("run_evidence_graph_nodes_or_edges_invalid")
    if nodes != _canonicalize_nodes(nodes):
        raise ValueError("run_evidence_graph_nodes_not_canonical")
    if edges != _canonicalize_edges(edges):
        raise ValueError("run_evidence_graph_edges_not_canonical")

    node_ids = _validate_nodes(nodes=nodes, source_ids=source_ids)
    _validate_edges(edges=edges, node_ids=node_ids, source_ids=source_ids)

    node_count = payload.get("node_count")
    edge_count = payload.get("edge_count")
    if type(node_count) is not int or node_count != len(nodes):
        raise ValueError("run_evidence_graph_node_count_invalid")
    if type(edge_count) is not int or edge_count != len(edges):
        raise ValueError("run_evidence_graph_edge_count_invalid")

    if graph_result == "complete":
        if issues:
            raise ValueError("run_evidence_graph_complete_issues_present")
        if any(str(item.get("status") or "").strip() != "present" for item in source_summaries):
            raise ValueError("run_evidence_graph_complete_source_status_invalid")
        if not nodes:
            raise ValueError("run_evidence_graph_complete_nodes_missing")
        return

    if graph_result == "degraded":
        has_non_present_source = any(str(item.get("status") or "").strip() != "present" for item in source_summaries)
        if not issues and not has_non_present_source:
            raise ValueError("run_evidence_graph_degraded_basis_missing")
        if not nodes:
            raise ValueError("run_evidence_graph_degraded_nodes_missing")
        return

    if nodes or edges:
        raise ValueError("run_evidence_graph_blocked_artifact_shell_invalid")
    if not issues:
        raise ValueError("run_evidence_graph_blocked_reason_required")


def _validate_source_summaries(source_summaries: list[dict[str, Any]]) -> set[str]:
    source_ids: set[str] = set()
    for item in source_summaries:
        if not isinstance(item, dict):
            raise ValueError("run_evidence_graph_source_summary_invalid")
        source_id = str(item.get("source_id") or "").strip()
        authority_level = str(item.get("authority_level") or "").strip()
        source_kind = str(item.get("source_kind") or "").strip()
        status = str(item.get("status") or "").strip()
        if not source_id:
            raise ValueError("run_evidence_graph_source_id_required")
        if source_id in source_ids:
            raise ValueError("run_evidence_graph_source_id_duplicate")
        if authority_level not in _AUTHORITY_LEVELS:
            raise ValueError("run_evidence_graph_source_authority_level_invalid")
        if not source_kind:
            raise ValueError("run_evidence_graph_source_kind_required")
        if status not in _SOURCE_STATUSES:
            raise ValueError("run_evidence_graph_source_status_invalid")
        source_ids.add(source_id)
    return source_ids


def _validate_issues(*, issues: list[dict[str, Any]], source_ids: set[str]) -> None:
    for item in issues:
        if not isinstance(item, dict):
            raise ValueError("run_evidence_graph_issue_invalid")
        code = str(item.get("code") or "").strip()
        detail = str(item.get("detail") or "").strip()
        issue_source_id = str(item.get("source_id") or "").strip()
        if not code or not detail:
            raise ValueError("run_evidence_graph_issue_contract_invalid")
        if issue_source_id and issue_source_id not in source_ids:
            raise ValueError("run_evidence_graph_issue_source_missing")


def _validate_nodes(*, nodes: list[dict[str, Any]], source_ids: set[str]) -> set[str]:
    node_ids: set[str] = set()
    for item in nodes:
        if not isinstance(item, dict):
            raise ValueError("run_evidence_graph_node_invalid")
        node_id = str(item.get("id") or "").strip()
        family = str(item.get("family") or "").strip()
        node_source_ids = _validate_source_refs(item.get("source_ids"), source_ids=source_ids)
        if not node_id or family not in _NODE_FAMILIES:
            raise ValueError("run_evidence_graph_node_contract_invalid")
        if node_id in node_ids:
            raise ValueError("run_evidence_graph_node_duplicate")
        if not node_source_ids:
            raise ValueError("run_evidence_graph_node_sources_missing")
        node_ids.add(node_id)
    return node_ids


def _validate_edges(*, edges: list[dict[str, Any]], node_ids: set[str], source_ids: set[str]) -> None:
    edge_ids: set[str] = set()
    for item in edges:
        if not isinstance(item, dict):
            raise ValueError("run_evidence_graph_edge_invalid")
        edge_id = str(item.get("id") or "").strip()
        family = str(item.get("family") or "").strip()
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        edge_source_ids = _validate_source_refs(item.get("source_ids"), source_ids=source_ids)
        if not edge_id or family not in _EDGE_FAMILIES:
            raise ValueError("run_evidence_graph_edge_contract_invalid")
        if edge_id in edge_ids:
            raise ValueError("run_evidence_graph_edge_duplicate")
        if source not in node_ids or target not in node_ids:
            raise ValueError("run_evidence_graph_edge_endpoint_missing")
        if not edge_source_ids:
            raise ValueError("run_evidence_graph_edge_sources_missing")
        edge_ids.add(edge_id)


def _validate_source_refs(value: Any, *, source_ids: set[str]) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("run_evidence_graph_source_refs_invalid")
    normalized = [str(item).strip() for item in value]
    if any(not token for token in normalized):
        raise ValueError("run_evidence_graph_source_refs_invalid")
    if normalized != sorted(normalized):
        raise ValueError("run_evidence_graph_source_refs_not_canonical")
    if len(set(normalized)) != len(normalized):
        raise ValueError("run_evidence_graph_source_refs_duplicate")
    if any(token not in source_ids for token in normalized):
        raise ValueError("run_evidence_graph_source_ref_missing")
    return normalized


def _canonicalize_selected_views(values: list[str]) -> list[str]:
    normalized = [str(item).strip() for item in values]
    if any(not token for token in normalized):
        raise ValueError("run_evidence_graph_selected_views_invalid")
    if len(set(normalized)) != len(normalized):
        raise ValueError("run_evidence_graph_selected_views_duplicate")
    unknown = sorted(set(normalized).difference(RUN_EVIDENCE_GRAPH_VIEW_ORDER))
    if unknown:
        raise ValueError("run_evidence_graph_selected_view_invalid")
    normalized_set = set(normalized)
    return [view for view in RUN_EVIDENCE_GRAPH_VIEW_ORDER if view in normalized_set]


def _canonicalize_source_summaries(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("run_evidence_graph_source_summary_invalid")
        row = dict(value)
        row["source_id"] = str(row.get("source_id") or "").strip()
        row["authority_level"] = str(row.get("authority_level") or "").strip()
        row["source_kind"] = str(row.get("source_kind") or "").strip()
        row["status"] = str(row.get("status") or "").strip()
        if "source_ref" in row:
            row["source_ref"] = str(row.get("source_ref") or "").strip()
        if "detail" in row:
            row["detail"] = str(row.get("detail") or "").strip()
        rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("source_id") or ""))


def _canonicalize_issues(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("run_evidence_graph_issue_invalid")
        row = dict(value)
        row["code"] = str(row.get("code") or "").strip()
        row["detail"] = str(row.get("detail") or "").strip()
        if "source_id" in row:
            row["source_id"] = str(row.get("source_id") or "").strip()
        rows.append(row)
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("code") or ""),
            str(row.get("detail") or ""),
            str(row.get("source_id") or ""),
        ),
    )


def _canonicalize_nodes(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("run_evidence_graph_node_invalid")
        row = dict(value)
        row["id"] = str(row.get("id") or "").strip()
        row["family"] = str(row.get("family") or "").strip()
        row["source_ids"] = _canonicalize_source_id_list(row.get("source_ids"))
        if "label" in row:
            row["label"] = str(row.get("label") or "").strip()
        rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("id") or ""))


def _canonicalize_edges(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("run_evidence_graph_edge_invalid")
        row = dict(value)
        row["id"] = str(row.get("id") or "").strip()
        row["family"] = str(row.get("family") or "").strip()
        row["source"] = str(row.get("source") or "").strip()
        row["target"] = str(row.get("target") or "").strip()
        row["source_ids"] = _canonicalize_source_id_list(row.get("source_ids"))
        if "label" in row:
            row["label"] = str(row.get("label") or "").strip()
        rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("id") or ""))


def _canonicalize_source_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("run_evidence_graph_source_refs_invalid")
    return sorted(str(item).strip() for item in value)
