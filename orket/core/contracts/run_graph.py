"""Pure protocol graph projection over an explicit captured JSON event sequence."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from orket.core.contracts.protocol_hashing import canonical_json, hash_canonical_json
from orket.core.contracts.run_graph_contract import RUN_GRAPH_SCHEMA_VERSION, validate_run_graph_payload


def _sequence(event):
    return int(event.get("event_seq") or event.get("sequence_number") or 0)


def _safe_token(value):
    normalized = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("_") or "unknown"


def reconstruct_run_graph(events: list[dict[str, Any]], *, session_id: str | None = None) -> dict[str, Any]:
    # Canonical JSON captures nested values without effectful object __str__ fallbacks.
    ordered = json.loads(canonical_json([event for event in events if isinstance(event, dict)]))
    ordered.sort(key=lambda event: (_sequence(event), str(event.get("kind") or "")))
    run_id = str(session_id or "").strip()
    if not run_id:
        run_id = next((str(e.get("run_id") or e.get("session_id") or "").strip()
                       for e in ordered if str(e.get("run_id") or e.get("session_id") or "").strip()), "unknown-run")
    graph = _Graph(run_id)
    for event in ordered:
        graph.include(event)
    return graph.payload(ordered)


@dataclass
class _Graph:
    run_id: str
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[tuple, dict] = field(default_factory=dict)
    stages: dict[str, str] = field(default_factory=dict)
    calls: dict[int, str] = field(default_factory=dict)
    call_order: list[int] = field(default_factory=list)

    def __post_init__(self):
        self.root = f"workload_stage:{_safe_token(self.run_id)}:root"
        self.nodes[self.root] = {"id": self.root, "type": "workload_stage", "run_id": self.run_id,
                                 "stage_id": "root", "label": self.run_id}
        self.stages[""] = self.root

    def include(self, event):
        kind, sequence = str(event.get("kind") or "").strip(), _sequence(event)
        if sequence <= 0:
            return
        if kind in {"run_started", "run_finalized"}:
            name = str(event.get("run_name") or "").strip()
            if kind == "run_started" and name:
                self.nodes[self.root]["label"] = name
            self._artifacts(event, kind, sequence)
        elif kind == "tool_call":
            self._call(event, sequence)
        elif kind in {"operation_result", "tool_result"}:
            self._result(event, kind, sequence)

    def _edge(self, kind, source, target, ordinal):
        key = (str(kind), str(source), str(target), int(ordinal))
        self.edges.setdefault(key, {"type": key[0], "source": key[1], "target": key[2], "ordinal": key[3]})

    def _stage(self, step_id):
        if step_id not in self.stages:
            stage = f"workload_stage:{_safe_token(self.run_id)}:{_safe_token(step_id)}"
            self.stages[step_id] = stage
            self.nodes[stage] = {"id": stage, "type": "workload_stage", "run_id": self.run_id,
                                 "stage_id": step_id, "label": step_id}
        return self.stages[step_id]

    def _call(self, event, sequence):
        step_id = str(event.get("step_id") or "").strip()
        stage, identity = self._stage(step_id), f"tool_call:{sequence}"
        node = {"id": identity, "type": "tool_call", "event_seq": sequence,
                "tool_name": str(event.get("tool_name") or event.get("tool") or "").strip(),
                "operation_id": str(event.get("operation_id") or "").strip(), "step_id": step_id,
                "tool_call_hash": str(event.get("tool_call_hash") or "").strip()}
        manifest = event.get("tool_invocation_manifest")
        if isinstance(manifest, dict):
            node["manifest_hash"] = str(manifest.get("manifest_hash") or "").strip()
            node["determinism_class"] = str(manifest.get("determinism_class") or "").strip()
            for key in ("control_plane_run_id", "control_plane_attempt_id", "control_plane_step_id",
                        "control_plane_reservation_id", "control_plane_lease_id", "control_plane_resource_id"):
                token = str(manifest.get(key) or "").strip()
                if token:
                    node[key] = token
        self.nodes[identity] = node
        self.calls[sequence] = identity
        self.call_order.append(sequence)
        self._edge("execution_order", stage, identity, sequence)

    def _result(self, event, kind, sequence):
        call_sequence = int(event.get("call_sequence_number") or 0)
        result = event.get("result")
        result = result if isinstance(result, dict) else {}
        identity = f"artifact:tool_result:{sequence}"
        self.nodes[identity] = {"id": identity, "type": "artifact", "artifact_kind": kind,
                                "event_seq": sequence, "call_sequence_number": call_sequence,
                                "operation_id": str(event.get("operation_id") or "").strip(),
                                "tool_name": str(event.get("tool_name") or event.get("tool") or "").strip(),
                                "ok": bool(result.get("ok", False)), "artifact_digest": hash_canonical_json(result)}
        call = self.calls.get(call_sequence)
        if call is not None:
            self._edge("call_result", call, identity, sequence)
            self._edge("artifact_produced", call, identity, sequence)
        compatibility = result.get("compat_translation")
        if isinstance(compatibility, dict):
            self._compatibility(compatibility, call_sequence, sequence, call)

    def _compatibility(self, value, call_sequence, sequence, call):
        identity = f"compat_mapping:{call_sequence or sequence}"
        self.nodes[identity] = {
            "id": identity, "type": "compat_mapping", "compat_tool_name": str(value.get("compat_tool_name") or "").strip(),
            "mapping_version": value.get("mapping_version"),
            "mapping_determinism": str(value.get("mapping_determinism") or "").strip(),
            "schema_compatibility_range": str(value.get("schema_compatibility_range") or "").strip(),
            "mapped_core_tools": [str(item).strip() for item in list(value.get("mapped_core_tools") or []) if str(item).strip()],
            "translation_hash": str(value.get("translation_hash") or "").strip(),
        }
        if call is not None:
            self._edge("compat_expansion", call, identity, sequence)
        artifact = f"artifact:compat_translation:{sequence}"
        self.nodes[artifact] = {"id": artifact, "type": "artifact", "artifact_kind": "compat_translation",
                                "event_seq": sequence,
                                "artifact_digest": hash_canonical_json(value),
                                "compat_tool_name": str(value.get("compat_tool_name") or "").strip()}
        self._edge("artifact_produced", identity, artifact, sequence)

    def _artifacts(self, event, kind, sequence):
        artifacts = event.get("artifacts")
        if not isinstance(artifacts, dict):
            return
        for name in sorted(artifacts):
            value = artifacts[name]
            identity = f"artifact:{kind}:{sequence}:{_safe_token(name)}"
            self.nodes[identity] = {"id": identity, "type": "artifact", "artifact_kind": f"{kind}.artifact",
                                    "artifact_name": name, "source_event_seq": sequence,
                                    "artifact_digest": hash_canonical_json(value)}
            if isinstance(value, str):
                self.nodes[identity]["artifact_ref"] = value
            self._edge("artifact_produced", self.root, identity, sequence)

    def payload(self, events):
        calls = sorted(self.call_order)
        for previous, current in zip(calls, calls[1:], strict=False):
            self._edge("execution_order", self.calls[previous], self.calls[current], current)
        nodes = sorted(self.nodes.values(), key=lambda row: str(row.get("id") or ""))
        edges = sorted(self.edges.values(), key=lambda row: (
            str(row.get("type") or ""), str(row.get("source") or ""), str(row.get("target") or ""), int(row.get("ordinal") or 0)))
        versions = sorted({str(e.get("ledger_schema_version") or "1.0").strip() for e in events
                           if str(e.get("ledger_schema_version") or "1.0").strip()})
        schema = "1.0" if not versions else versions[0] if len(versions) == 1 else "mixed"
        payload = {"run_graph_schema_version": RUN_GRAPH_SCHEMA_VERSION, "run_id": self.run_id,
                   "derived_from": {"source_of_truth": "ledger+artifacts", "ledger_event_count": len(events),
                                    "ledger_schema_version": schema},
                   "node_count": len(nodes), "edge_count": len(edges), "nodes": nodes, "edges": edges,
                   "graph_digest": hash_canonical_json({"run_id": self.run_id, "nodes": nodes, "edges": edges})}
        validate_run_graph_payload(payload)
        return payload
