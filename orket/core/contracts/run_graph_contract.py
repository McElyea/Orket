"""Value-only vocabulary and structural validation for the protocol run graph."""
from typing import Any

RUN_GRAPH_SCHEMA_VERSION = "1.0"
_NODE_TYPES = frozenset({"tool_call", "compat_mapping", "workload_stage", "artifact"})
_EDGE_TYPES = frozenset({"call_result", "artifact_produced", "compat_expansion", "execution_order"})


def validate_run_graph_payload(payload: dict[str, Any]) -> None:
    schema_version = str(payload.get("run_graph_schema_version") or "").strip()
    if schema_version != RUN_GRAPH_SCHEMA_VERSION:
        raise ValueError("run_graph_schema_version_invalid")
    nodes, edges = payload.get("nodes"), payload.get("edges")
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
        if str(node.get("type") or "") == "artifact" and str(node.get("id") or "").strip() not in artifact_targets:
            raise ValueError("run_graph_artifact_lineage_missing")
