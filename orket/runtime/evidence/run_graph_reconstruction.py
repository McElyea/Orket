from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.application.workflows.protocol_hashing import hash_canonical_json

RUN_GRAPH_SCHEMA_VERSION = "1.0"
_TOOL_RESULT_KINDS = {"operation_result", "tool_result"}
_NODE_TYPES = {"tool_call", "compat_mapping", "workload_stage", "artifact"}
_EDGE_TYPES = {"call_result", "artifact_produced", "compat_expansion", "execution_order"}


def reconstruct_run_graph(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    ordered_events = _ordered_events(events)
    run_id = _resolve_run_id(events=ordered_events, session_id=session_id)
    root_stage_id = f"workload_stage:{_safe_token(run_id)}:root"

    nodes: dict[str, dict[str, Any]] = {
        root_stage_id: {
            "id": root_stage_id,
            "type": "workload_stage",
            "run_id": run_id,
            "stage_id": "root",
            "label": run_id,
        }
    }
    edges: dict[tuple[str, str, str, int], dict[str, Any]] = {}
    stage_nodes: dict[str, str] = {"": root_stage_id}
    call_nodes: dict[int, str] = {}
    call_sequences: list[int] = []

    for event in ordered_events:
        kind = str(event.get("kind") or "").strip()
        event_seq = _event_sequence(event)
        if event_seq <= 0:
            continue
        if kind == "run_started":
            run_name = str(event.get("run_name") or "").strip()
            if run_name:
                nodes[root_stage_id]["label"] = run_name
            _add_run_artifact_nodes(
                event=event,
                source_stage_id=root_stage_id,
                nodes=nodes,
                edges=edges,
            )
            continue
        if kind == "run_finalized":
            _add_run_artifact_nodes(
                event=event,
                source_stage_id=root_stage_id,
                nodes=nodes,
                edges=edges,
            )
            continue
        if kind == "tool_call":
            step_id = str(event.get("step_id") or "").strip()
            stage_id = _resolve_stage_node(
                run_id=run_id,
                step_id=step_id,
                stage_nodes=stage_nodes,
                nodes=nodes,
            )
            call_id = f"tool_call:{event_seq}"
            call_node = {
                "id": call_id,
                "type": "tool_call",
                "event_seq": event_seq,
                "tool_name": str(event.get("tool_name") or event.get("tool") or "").strip(),
                "operation_id": str(event.get("operation_id") or "").strip(),
                "step_id": step_id,
                "tool_call_hash": str(event.get("tool_call_hash") or "").strip(),
            }
            manifest = event.get("tool_invocation_manifest")
            if isinstance(manifest, dict):
                call_node["manifest_hash"] = str(manifest.get("manifest_hash") or "").strip()
                call_node["determinism_class"] = str(manifest.get("determinism_class") or "").strip()
                for field in (
                    "control_plane_run_id",
                    "control_plane_attempt_id",
                    "control_plane_step_id",
                    "control_plane_reservation_id",
                    "control_plane_lease_id",
                    "control_plane_resource_id",
                ):
                    token = str(manifest.get(field) or "").strip()
                    if token:
                        call_node[field] = token
            nodes[call_id] = call_node
            call_nodes[event_seq] = call_id
            call_sequences.append(event_seq)
            _add_edge(
                edges=edges,
                edge_type="execution_order",
                source=stage_id,
                target=call_id,
                ordinal=event_seq,
            )
            continue
        if kind in _TOOL_RESULT_KINDS:
            call_sequence_number = int(event.get("call_sequence_number") or 0)
            result_payload = event.get("result")
            result_payload = result_payload if isinstance(result_payload, dict) else {}
            result_id = f"artifact:tool_result:{event_seq}"
            nodes[result_id] = {
                "id": result_id,
                "type": "artifact",
                "artifact_kind": kind,
                "event_seq": event_seq,
                "call_sequence_number": call_sequence_number,
                "operation_id": str(event.get("operation_id") or "").strip(),
                "tool_name": str(event.get("tool_name") or event.get("tool") or "").strip(),
                "ok": bool(result_payload.get("ok", False)),
                "artifact_digest": hash_canonical_json(result_payload),
            }
            linked_call_id = call_nodes.get(call_sequence_number)
            if linked_call_id is not None:
                _add_edge(
                    edges=edges,
                    edge_type="call_result",
                    source=linked_call_id,
                    target=result_id,
                    ordinal=event_seq,
                )
                _add_edge(
                    edges=edges,
                    edge_type="artifact_produced",
                    source=linked_call_id,
                    target=result_id,
                    ordinal=event_seq,
                )
            compat_translation = result_payload.get("compat_translation")
            if not isinstance(compat_translation, dict):
                continue
            compat_node_id = f"compat_mapping:{call_sequence_number or event_seq}"
            nodes[compat_node_id] = {
                "id": compat_node_id,
                "type": "compat_mapping",
                "compat_tool_name": str(compat_translation.get("compat_tool_name") or "").strip(),
                "mapping_version": compat_translation.get("mapping_version"),
                "mapping_determinism": str(compat_translation.get("mapping_determinism") or "").strip(),
                "schema_compatibility_range": str(compat_translation.get("schema_compatibility_range") or "").strip(),
                "mapped_core_tools": [
                    str(item).strip()
                    for item in list(compat_translation.get("mapped_core_tools") or [])
                    if str(item).strip()
                ],
                "translation_hash": str(compat_translation.get("translation_hash") or "").strip(),
            }
            if linked_call_id is not None:
                _add_edge(
                    edges=edges,
                    edge_type="compat_expansion",
                    source=linked_call_id,
                    target=compat_node_id,
                    ordinal=event_seq,
                )
            compat_artifact_id = f"artifact:compat_translation:{event_seq}"
            nodes[compat_artifact_id] = {
                "id": compat_artifact_id,
                "type": "artifact",
                "artifact_kind": "compat_translation",
                "event_seq": event_seq,
                "artifact_digest": hash_canonical_json(compat_translation),
                "compat_tool_name": str(compat_translation.get("compat_tool_name") or "").strip(),
            }
            _add_edge(
                edges=edges,
                edge_type="artifact_produced",
                source=compat_node_id,
                target=compat_artifact_id,
                ordinal=event_seq,
            )

    sorted_call_sequences = sorted(call_sequences)
    for index in range(1, len(sorted_call_sequences)):
        previous_seq = sorted_call_sequences[index - 1]
        current_seq = sorted_call_sequences[index]
        previous_call_id = call_nodes.get(previous_seq)
        current_call_id = call_nodes.get(current_seq)
        if previous_call_id is None or current_call_id is None:
            continue
        _add_edge(
            edges=edges,
            edge_type="execution_order",
            source=previous_call_id,
            target=current_call_id,
            ordinal=current_seq,
        )

    node_rows = sorted(nodes.values(), key=lambda row: str(row.get("id") or ""))
    edge_rows = sorted(
        edges.values(),
        key=lambda row: (
            str(row.get("type") or ""),
            str(row.get("source") or ""),
            str(row.get("target") or ""),
            int(row.get("ordinal") or 0),
        ),
    )
    payload = {
        "run_graph_schema_version": RUN_GRAPH_SCHEMA_VERSION,
        "run_id": run_id,
        "derived_from": {
            "source_of_truth": "ledger+artifacts",
            "ledger_event_count": len(ordered_events),
            "ledger_schema_version": _ledger_schema_version(ordered_events),
        },
        "node_count": len(node_rows),
        "edge_count": len(edge_rows),
        "nodes": node_rows,
        "edges": edge_rows,
    }
    payload["graph_digest"] = hash_canonical_json(
        {
            "run_id": run_id,
            "nodes": node_rows,
            "edges": edge_rows,
        }
    )
    validate_run_graph_payload(payload)
    return payload


def reconstruct_run_graph_from_events_log(
    *,
    events_log_path: Path,
    session_id: str | None = None,
) -> dict[str, Any]:
    events = AppendOnlyRunLedger(Path(events_log_path)).replay_events()
    resolved_session_id = str(session_id or "").strip()
    if not resolved_session_id:
        resolved_session_id = str(Path(events_log_path).parent.name).strip()
    return reconstruct_run_graph(events, session_id=resolved_session_id)


def write_run_graph_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    validate_run_graph_payload(payload)
    run_graph_path = Path(root) / "runs" / str(session_id).strip() / "run_graph.json"
    run_graph_path.parent.mkdir(parents=True, exist_ok=True)
    run_graph_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return run_graph_path


def validate_run_graph_payload(payload: dict[str, Any]) -> None:
    schema_version = str(payload.get("run_graph_schema_version") or "").strip()
    if schema_version != RUN_GRAPH_SCHEMA_VERSION:
        raise ValueError("run_graph_schema_version_invalid")
    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("run_graph_nodes_or_edges_invalid")
    node_ids: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("run_graph_node_invalid")
        node_id = str(node.get("id") or "").strip()
        node_type = str(node.get("type") or "").strip()
        if not node_id or node_type not in _NODE_TYPES:
            raise ValueError("run_graph_node_contract_invalid")
        if node_id in node_ids:
            raise ValueError("run_graph_node_duplicate")
        node_ids.add(node_id)
    artifact_targets: set[str] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("run_graph_edge_invalid")
        edge_type = str(edge.get("type") or "").strip()
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if edge_type not in _EDGE_TYPES:
            raise ValueError("run_graph_edge_type_invalid")
        if source not in node_ids or target not in node_ids:
            raise ValueError("run_graph_edge_endpoint_missing")
        if edge_type == "artifact_produced":
            artifact_targets.add(target)
    for node in nodes:
        if str(node.get("type") or "") != "artifact":
            continue
        node_id = str(node.get("id") or "").strip()
        if node_id not in artifact_targets:
            raise ValueError("run_graph_artifact_lineage_missing")


def _resolve_run_id(*, events: list[dict[str, Any]], session_id: str | None) -> str:
    explicit_session_id = str(session_id or "").strip()
    if explicit_session_id:
        return explicit_session_id
    for event in events:
        run_id = str(event.get("run_id") or event.get("session_id") or "").strip()
        if run_id:
            return run_id
    return "unknown-run"


def _event_sequence(event: dict[str, Any]) -> int:
    return int(event.get("event_seq") or event.get("sequence_number") or 0)


def _ordered_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(event or {}) for event in events if isinstance(event, dict)]
    rows.sort(key=lambda event: (_event_sequence(event), str(event.get("kind") or "")))
    return rows


def _ledger_schema_version(events: list[dict[str, Any]]) -> str:
    versions = sorted(
        {
            str(event.get("ledger_schema_version") or "1.0").strip()
            for event in events
            if str(event.get("ledger_schema_version") or "1.0").strip()
        }
    )
    if not versions:
        return "1.0"
    return versions[0] if len(versions) == 1 else "mixed"


def _resolve_stage_node(
    *,
    run_id: str,
    step_id: str,
    stage_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
) -> str:
    normalized_step_id = str(step_id or "").strip()
    if normalized_step_id in stage_nodes:
        return stage_nodes[normalized_step_id]
    stage_id = f"workload_stage:{_safe_token(run_id)}:{_safe_token(normalized_step_id)}"
    stage_nodes[normalized_step_id] = stage_id
    nodes[stage_id] = {
        "id": stage_id,
        "type": "workload_stage",
        "run_id": run_id,
        "stage_id": normalized_step_id,
        "label": normalized_step_id,
    }
    return stage_id


def _add_run_artifact_nodes(
    *,
    event: dict[str, Any],
    source_stage_id: str,
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str, int], dict[str, Any]],
) -> None:
    kind = str(event.get("kind") or "").strip()
    event_seq = _event_sequence(event)
    artifacts = event.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    for artifact_name in sorted(artifacts.keys()):
        artifact_value = artifacts.get(artifact_name)
        artifact_id = f"artifact:{kind}:{event_seq}:{_safe_token(str(artifact_name))}"
        nodes[artifact_id] = {
            "id": artifact_id,
            "type": "artifact",
            "artifact_kind": f"{kind}.artifact",
            "artifact_name": str(artifact_name),
            "source_event_seq": event_seq,
            "artifact_digest": hash_canonical_json(
                artifact_value
                if isinstance(artifact_value, (dict, list, str, int, float, bool)) or artifact_value is None
                else str(artifact_value)
            ),
        }
        if isinstance(artifact_value, str):
            nodes[artifact_id]["artifact_ref"] = artifact_value
        _add_edge(
            edges=edges,
            edge_type="artifact_produced",
            source=source_stage_id,
            target=artifact_id,
            ordinal=event_seq,
        )


def _add_edge(
    *,
    edges: dict[tuple[str, str, str, int], dict[str, Any]],
    edge_type: str,
    source: str,
    target: str,
    ordinal: int,
) -> None:
    key = (
        str(edge_type),
        str(source),
        str(target),
        int(ordinal),
    )
    if key in edges:
        return
    edges[key] = {
        "type": str(edge_type),
        "source": str(source),
        "target": str(target),
        "ordinal": int(ordinal),
    }


def _safe_token(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "unknown"
    return re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("_") or "unknown"
