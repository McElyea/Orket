"""Operator graph projection of inspected retained acceptance and observed edges."""
from __future__ import annotations

import heapq
import logging
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.card_completion_outcome_service import project_card_completion
from orket.application.services.card_dependency_service import inspect_card_dependencies
from orket.application.services.card_workspace_mutation_service import CardWorkspaceMutationService
from orket.core.contracts.repositories import CardRepository


async def inspect_execution_graph(*, cards: CardRepository, session_id: str) -> dict[str, Any]:
    nodes = []
    async with cards.completion_write_guard():
        backlog = await cards.get_by_session(session_id)
        displayed = {record.id for record in backlog}
        for index, record in enumerate(backlog):
            dependencies = await inspect_card_dependencies(cards=cards, record=record)
            completion = await project_card_completion(cards=cards, record=record)
            blocked_by = dependencies["unresolved_dependencies"]
            nodes.append({
                "id": record.id, "summary": record.summary, "seat": record.seat, "status": record.status.value,
                **dependencies, "blocked": bool(blocked_by), "blocked_by": blocked_by,
                "unresolved_dependencies": [dep for dep in record.depends_on if dep not in displayed],
                **completion, "order_index": index,
            })
    return _project_graph(nodes)


def _project_graph(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    index = {node["id"]: node["order_index"] for node in nodes}
    adjacency: dict[str, list[str]] = {card_id: [] for card_id in index}
    in_degree = dict.fromkeys(index, 0)
    edges = []
    for node in nodes:
        for dep in node["depends_on"]:
            if dep in index:
                edges.append({"source": dep, "target": node["id"], "kind": "depends_on"})
                adjacency[dep].append(node["id"])
                in_degree[node["id"]] += 1
    remaining = dict(in_degree)
    ready = [(index[card_id], card_id) for card_id, degree in remaining.items() if degree == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, current = heapq.heappop(ready)
        order.append(current)
        for neighbor in adjacency[current]:
            remaining[neighbor] -= 1
            if remaining[neighbor] == 0:
                heapq.heappush(ready, (index[neighbor], neighbor))
    for node in nodes:
        node["in_degree"] = in_degree[node["id"]]
    return {"nodes": nodes, "edges": edges, "execution_order": order,
            "has_cycle": len(order) != len(index),
            "cycle_nodes": [card_id for card_id, degree in remaining.items() if degree > 0]}


def execution_graph_payload(
    *, session_id: str, graph: dict[str, Any], handoffs: list[dict[str, Any]],
) -> dict[str, Any]:
    edges = list(graph["edges"])
    keys = {(edge["source"], edge["target"], edge["kind"]) for edge in edges}
    for edge in handoffs:
        key = (edge["source"], edge["target"], edge["kind"])
        if key not in keys:
            edges.append(edge)
            keys.add(key)
    return {**graph, "session_id": session_id, "node_count": len(graph["nodes"]), "edge_count": len(edges),
            "edges_detailed": edges, "edges": [{"source": e["source"], "target": e["target"]} for e in edges]}


async def persist_execution_graph_snapshot(
    *, cards: CardRepository, run_path: Path, payload: dict[str, Any],
) -> None:
    async def write_snapshot() -> str:
        return await AsyncFileTools(run_path).write_file(
            "agent_output/observability/execution_graph_snapshot.json", payload,
        )

    try:
        await CardWorkspaceMutationService(cards).run(write_snapshot)
    except (OSError, TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Execution graph snapshot persistence failed for session %s", payload["session_id"], exc_info=True,
        )
