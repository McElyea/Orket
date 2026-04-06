from __future__ import annotations

import asyncio
import html
import re
from pathlib import Path
from typing import Any

import aiofiles

from orket.runtime.run_evidence_graph import validate_run_evidence_graph_payload

_VIEW_TITLES = {
    "full_lineage": "Full Lineage",
    "failure_path": "Failure Path",
    "authority": "Authority",
    "decision": "Decision",
    "resource_authority_path": "Resource Authority Path",
    "closure_path": "Closure Path",
}

_VIEW_QUESTIONS = {
    "full_lineage": "What authoritative run-evidence lineage exists for the selected run?",
    "failure_path": "Where did failure, interruption, or recovery change the path?",
    "authority": "What authority chain allowed or blocked mutation and closure?",
    "decision": "Where did routing, policy, supervisor, recovery, or reconciliation decisions change the path?",
    "resource_authority_path": "What ownership path governed reservation, lease, resource, and mutation authority?",
    "closure_path": "What exact chain closed the run?",
}


def build_run_evidence_graph_views(payload: dict[str, Any]) -> list[dict[str, Any]]:
    validate_run_evidence_graph_payload(payload)
    nodes = [node for node in payload.get("nodes", []) if isinstance(node, dict)]
    edges = [edge for edge in payload.get("edges", []) if isinstance(edge, dict)]
    node_by_id = {str(node.get("id") or ""): node for node in nodes}
    family_nodes = _nodes_by_family(nodes)

    views: list[dict[str, Any]] = []
    for view_name in payload.get("selected_views", []):
        view_token = str(view_name)
        node_ids = _select_view_node_ids(
            view_name=view_token,
            node_by_id=node_by_id,
            family_nodes=family_nodes,
        )
        view_nodes = [node for node in nodes if str(node.get("id") or "") in node_ids]
        view_edges = [
            edge
            for edge in edges
            if str(edge.get("source") or "") in node_ids and str(edge.get("target") or "") in node_ids
        ]
        views.append(
            {
                "view": view_token,
                "title": _VIEW_TITLES[view_token],
                "operator_question": _VIEW_QUESTIONS[view_token],
                "node_count": len(view_nodes),
                "edge_count": len(view_edges),
                "nodes": view_nodes,
                "edges": view_edges,
            }
        )
    return views


def build_run_evidence_graph_mermaid(payload: dict[str, Any]) -> str:
    validate_run_evidence_graph_payload(payload)
    views = build_run_evidence_graph_views(payload)
    lines = [
        "flowchart TD",
        f"%% run_id: {payload['run_id']}",
        f"%% graph_result: {payload['graph_result']}",
    ]
    for issue in payload.get("issues", []):
        if not isinstance(issue, dict):
            continue
        lines.append(
            f"%% issue {str(issue.get('code') or '').strip()}: {str(issue.get('detail') or '').strip()}"
        )
    for view in views:
        if not view["nodes"]:
            lines.append(f"%% view {view['view']} has no semantic nodes")
            continue
        lines.append(f'  subgraph view_{view["view"]}["{view["title"]} | {view["operator_question"]}"]')
        for node in view["nodes"]:
            alias = _mermaid_alias(view=str(view["view"]), node_id=str(node.get("id") or ""))
            lines.append(f'    {alias}["{_mermaid_label(node)}"]')
        for edge in view["edges"]:
            source_alias = _mermaid_alias(view=str(view["view"]), node_id=str(edge.get("source") or ""))
            target_alias = _mermaid_alias(view=str(view["view"]), node_id=str(edge.get("target") or ""))
            lines.append(
                f"    {source_alias} -->|{_escape_mermaid(str(edge.get('family') or ''))}| {target_alias}"
            )
        lines.append("  end")
    return "\n".join(lines) + "\n"


def build_run_evidence_graph_html(payload: dict[str, Any]) -> str:
    validate_run_evidence_graph_payload(payload)
    views = build_run_evidence_graph_views(payload)
    issues = [issue for issue in payload.get("issues", []) if isinstance(issue, dict)]
    source_summaries = [
        summary for summary in payload.get("source_summaries", []) if isinstance(summary, dict)
    ]
    issue_rows = "".join(
        f"<li><strong>{html.escape(str(issue.get('code') or ''))}</strong>: "
        f"{html.escape(str(issue.get('detail') or ''))}</li>"
        for issue in issues
    )
    summary_rows = "".join(
        f"<li><strong>{html.escape(str(summary.get('source_kind') or ''))}</strong>: "
        f"{html.escape(str(summary.get('status') or ''))} "
        f"({html.escape(str(summary.get('source_ref') or ''))})</li>"
        for summary in source_summaries
    )
    view_rows = "".join(_build_html_view_section(view) for view in views)
    source_summary_html = summary_rows or '<li class="empty">No source summaries recorded.</li>'
    issues_html = issue_rows or '<li class="empty">No issues recorded.</li>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Run Evidence Graph | {html.escape(str(payload['run_id']))}</title>
  <style>:root {{ color-scheme: light; --ink: #122033; --muted: #5d6878; --line: #d2dae4; --panel: #f7f9fc; }} body {{ font-family: Consolas, 'Courier New', monospace; margin: 24px; color: var(--ink); background: #ffffff; }} h1, h2, h3 {{ margin: 0 0 12px; }} p, li {{ line-height: 1.4; }} .meta {{ display: grid; gap: 8px; margin: 0 0 20px; padding: 16px; border: 1px solid var(--line); background: var(--panel); }} .summary {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); margin-bottom: 24px; }} .card {{ padding: 16px; border: 1px solid var(--line); background: #ffffff; }} .view {{ margin-bottom: 24px; padding: 16px; border: 1px solid var(--line); background: var(--panel); }} .columns {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }} .pill {{ display: inline-block; padding: 2px 8px; border: 1px solid var(--line); margin-right: 8px; background: #fff; }} code {{ white-space: pre-wrap; word-break: break-word; }} ul {{ margin: 0; padding-left: 18px; }} .empty {{ color: var(--muted); }}</style>
</head>
<body>
  <h1>Run Evidence Graph</h1>
  <section class="meta">
    <div><span class="pill">run_id</span><code>{html.escape(str(payload['run_id']))}</code></div>
    <div><span class="pill">graph_result</span><strong>{html.escape(str(payload['graph_result']))}</strong></div>
    <div><span class="pill">generated</span><code>{html.escape(str(payload['generation_timestamp']))}</code></div>
    <div><span class="pill">selected_views</span><code>{html.escape(', '.join(payload.get('selected_views', [])))}</code></div>
  </section>
  <section class="summary">
    <div class="card"><h2>Source Summary</h2><ul>{source_summary_html}</ul></div>
    <div class="card"><h2>Issues</h2><ul>{issues_html}</ul></div>
  </section>
{view_rows}</body>
</html>
"""


async def write_run_evidence_graph_mermaid_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    return await _write_text_artifact(
        root=root,
        session_id=session_id,
        filename="run_evidence_graph.mmd",
        content=build_run_evidence_graph_mermaid(payload),
    )


async def write_run_evidence_graph_html_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    return await _write_text_artifact(
        root=root,
        session_id=session_id,
        filename="run_evidence_graph.html",
        content=build_run_evidence_graph_html(payload),
    )


async def write_run_evidence_graph_rendered_artifacts(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> dict[str, Path]:
    mermaid_path = await write_run_evidence_graph_mermaid_artifact(
        root=root, session_id=session_id, payload=payload
    )
    html_path = await write_run_evidence_graph_html_artifact(
        root=root, session_id=session_id, payload=payload
    )
    return {"mermaid_path": mermaid_path, "html_path": html_path}


async def _write_text_artifact(*, root: Path, session_id: str, filename: str, content: str) -> Path:
    artifact_path = Path(root) / "runs" / str(session_id).strip() / filename
    await asyncio.to_thread(artifact_path.parent.mkdir, parents=True, exist_ok=True)
    async with aiofiles.open(artifact_path, mode="w", encoding="utf-8") as handle:
        await handle.write(content)
    return artifact_path


def _build_html_view_section(view: dict[str, Any]) -> str:
    empty_nodes_html = '<li class="empty">No semantic nodes selected for this view.</li>'
    empty_edges_html = '<li class="empty">No semantic edges selected for this view.</li>'
    node_rows = "".join(
        f"<li><strong>{html.escape(str(node.get('family') or ''))}</strong>: "
        f"<code>{html.escape(str(node.get('label') or node.get('id') or ''))}</code></li>"
        for node in view["nodes"]
    )
    edge_rows = "".join(
        f"<li><strong>{html.escape(str(edge.get('family') or ''))}</strong>: "
        f"<code>{html.escape(str(edge.get('source') or ''))}</code> -> "
        f"<code>{html.escape(str(edge.get('target') or ''))}</code></li>"
        for edge in view["edges"]
    )
    return (
        "  <section class=\"view\">\n"
        f"    <h2>{html.escape(str(view['title']))}</h2>\n"
        f"    <p>{html.escape(str(view['operator_question']))}</p>\n"
        f"    <p><span class=\"pill\">nodes</span>{view['node_count']} "
        f"<span class=\"pill\">edges</span>{view['edge_count']}</p>\n"
        "    <div class=\"columns\">\n"
        "      <div class=\"card\">\n"
        "        <h3>Nodes</h3>\n"
        f"        <ul>{node_rows or empty_nodes_html}</ul>\n"
        "      </div>\n"
        "      <div class=\"card\">\n"
        "        <h3>Edges</h3>\n"
        f"        <ul>{edge_rows or empty_edges_html}</ul>\n"
        "      </div>\n"
        "    </div>\n"
        "  </section>\n"
    )


def _select_view_node_ids(
    *,
    view_name: str,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    if view_name == "full_lineage":
        return set(node_by_id)
    if view_name == "failure_path":
        return _failure_path_node_ids(node_by_id=node_by_id, family_nodes=family_nodes)
    if view_name == "authority":
        return _authority_node_ids(node_by_id=node_by_id, family_nodes=family_nodes)
    if view_name == "decision":
        return _decision_node_ids(node_by_id=node_by_id, family_nodes=family_nodes)
    if view_name == "resource_authority_path":
        return _resource_authority_path_node_ids(node_by_id=node_by_id, family_nodes=family_nodes)
    return _closure_path_node_ids(node_by_id=node_by_id, family_nodes=family_nodes)


def _failure_path_node_ids(
    *,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    recovery_nodes = family_nodes.get("recovery_decision", [])
    attempt_refs = {
        _record_ref(node)
        for node in family_nodes.get("attempt", [])
        if str(_attr(node, "attempt_state")).strip()
        and str(_attr(node, "attempt_state")).strip() != "attempt_completed"
    }
    for node in recovery_nodes:
        for field_name in ("failed_attempt_id", "new_attempt_id", "resumed_attempt_id"):
            token = str(_attr(node, field_name)).strip()
            if token:
                attempt_refs.add(token)
    if not attempt_refs and not recovery_nodes:
        return set()
    step_refs = {
        _record_ref(node)
        for node in family_nodes.get("step", [])
        if str(_attr(node, "attempt_id")).strip() in attempt_refs
    }
    checkpoint_refs = {
        _record_ref(node)
        for node in family_nodes.get("checkpoint", [])
        if str(_attr(node, "parent_ref")).strip() in step_refs
        or str(_attr(node, "parent_ref")).strip() in attempt_refs
    }
    selected = _node_ids_for_refs("attempt", attempt_refs)
    selected.update(_node_ids_for_refs("step", step_refs))
    selected.update(_node_ids_for_family(recovery_nodes))
    selected.update(_node_ids_for_refs("checkpoint", checkpoint_refs))
    selected.update(
        _node_ids_for_family(
            [
                node
                for node in family_nodes.get("checkpoint_acceptance", [])
                if str(_attr(node, "checkpoint_id")).strip() in checkpoint_refs
            ]
        )
    )
    selected.update(
        _node_ids_for_family(
            [node for node in family_nodes.get("effect", []) if str(_attr(node, "step_id")).strip() in step_refs]
        )
    )
    selected.update(
        _node_ids_for_family(
            [node for node in family_nodes.get("observation", []) if str(_attr(node, "step_id")).strip() in step_refs]
        )
    )
    run_refs = {
        str(_attr(node, "run_id")).strip()
        for node in recovery_nodes + family_nodes.get("final_truth", [])
        if str(_attr(node, "run_id")).strip()
    }
    selected.update(_node_ids_for_refs("run", run_refs))
    selected.update(_node_ids_for_family(family_nodes.get("final_truth", [])))
    selected.update(_node_ids_for_family(family_nodes.get("reconciliation", [])))
    for node in family_nodes.get("final_truth", []):
        observation_ref = str(_attr(node, "authoritative_result_ref")).strip()
        if _node_id("observation", observation_ref) in node_by_id:
            selected.add(_node_id("observation", observation_ref))
    selected.update(
        _matching_operator_action_node_ids(
            operator_nodes=family_nodes.get("operator_action", []),
            run_refs=run_refs,
            transition_refs=attempt_refs | step_refs,
            resource_refs=set(),
        )
    )
    return {node_id for node_id in selected if node_id in node_by_id}


def _authority_node_ids(
    *,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    selected = _node_ids_for_family(family_nodes.get("reservation", []))
    selected.update(_node_ids_for_family(family_nodes.get("lease", [])))
    selected.update(_node_ids_for_family(family_nodes.get("resource", [])))
    selected.update(_node_ids_for_family(family_nodes.get("reconciliation", [])))
    selected.update(_node_ids_for_family(family_nodes.get("final_truth", [])))
    selected.update(_node_ids_for_family(family_nodes.get("effect", [])))

    effect_step_refs = {
        str(_attr(node, "step_id")).strip()
        for node in family_nodes.get("effect", [])
        if str(_attr(node, "step_id")).strip()
    }
    authoritative_result_refs = {
        str(_attr(node, "authoritative_result_ref")).strip()
        for node in family_nodes.get("final_truth", [])
        if str(_attr(node, "authoritative_result_ref")).strip()
    }
    authority_observation_nodes = [
        node
        for node in family_nodes.get("observation", [])
        if str(_attr(node, "resource_id")).strip()
        or str(_attr(node, "final_truth_record_id")).strip()
        or str(_attr(node, "step_id")).strip() in effect_step_refs
        or str(_attr(node, "observation_ref")).strip() in authoritative_result_refs
    ]
    selected.update(_node_ids_for_family(authority_observation_nodes))

    step_refs = set(effect_step_refs)
    step_refs.update(
        str(_attr(node, "step_id")).strip()
        for node in authority_observation_nodes
        if str(_attr(node, "step_id")).strip()
    )
    step_refs.update(
        _record_ref(node)
        for node in family_nodes.get("step", [])
        if str(_attr(node, "output_ref")).strip() in authoritative_result_refs
    )
    attempt_refs = {
        str(_attr(node, "attempt_id")).strip()
        for node in family_nodes.get("step", [])
        if _record_ref(node) in step_refs and str(_attr(node, "attempt_id")).strip()
    }
    run_refs = {
        str(_attr(node, "run_id")).strip()
        for node in family_nodes.get("attempt", []) + family_nodes.get("final_truth", []) + family_nodes.get("reconciliation", [])
        if (
            _record_ref(node) in attempt_refs
            or node in family_nodes.get("final_truth", [])
            or node in family_nodes.get("reconciliation", [])
        )
        and str(_attr(node, "run_id")).strip()
    }
    resource_refs = {_record_ref(node) for node in family_nodes.get("resource", [])}

    selected.update(_node_ids_for_refs("step", step_refs))
    selected.update(_node_ids_for_refs("attempt", attempt_refs))
    selected.update(_node_ids_for_refs("run", run_refs))
    selected.update(
        _matching_operator_action_node_ids(
            operator_nodes=family_nodes.get("operator_action", []),
            run_refs=run_refs,
            transition_refs=attempt_refs | step_refs,
            resource_refs=resource_refs,
        )
    )
    return {node_id for node_id in selected if node_id in node_by_id}


def _decision_node_ids(
    *,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    checkpoint_acceptance_nodes = family_nodes.get("checkpoint_acceptance", [])
    recovery_nodes = family_nodes.get("recovery_decision", [])
    reconciliation_nodes = family_nodes.get("reconciliation", [])
    final_truth_nodes = family_nodes.get("final_truth", [])

    checkpoint_refs = {
        str(_attr(node, "checkpoint_id")).strip()
        for node in checkpoint_acceptance_nodes
        if str(_attr(node, "checkpoint_id")).strip()
    }
    selected_checkpoint_nodes = [
        node for node in family_nodes.get("checkpoint", []) if _record_ref(node) in checkpoint_refs
    ]
    selected = _node_ids_for_family(checkpoint_acceptance_nodes)
    selected.update(_node_ids_for_family(selected_checkpoint_nodes))
    selected.update(_node_ids_for_family(recovery_nodes))
    selected.update(_node_ids_for_family(reconciliation_nodes))
    selected.update(_node_ids_for_family(final_truth_nodes))

    authoritative_result_refs = {
        str(_attr(node, "authoritative_result_ref")).strip()
        for node in final_truth_nodes
        if str(_attr(node, "authoritative_result_ref")).strip()
    }
    step_refs = {
        str(_attr(node, "parent_ref")).strip()
        for node in selected_checkpoint_nodes
        if str(_attr(node, "parent_ref")).strip().startswith("kernel-action-run:")
        or ":step:" in str(_attr(node, "parent_ref")).strip()
    }
    step_refs.update(
        _record_ref(node)
        for node in family_nodes.get("step", [])
        if str(_attr(node, "output_ref")).strip() in authoritative_result_refs
    )
    attempt_refs = {
        str(_attr(node, "failed_attempt_id")).strip()
        for node in recovery_nodes
        if str(_attr(node, "failed_attempt_id")).strip()
    }
    attempt_refs.update(
        str(_attr(node, "new_attempt_id")).strip()
        for node in recovery_nodes
        if str(_attr(node, "new_attempt_id")).strip()
    )
    attempt_refs.update(
        str(_attr(node, "resumed_attempt_id")).strip()
        for node in recovery_nodes
        if str(_attr(node, "resumed_attempt_id")).strip()
    )
    attempt_refs.update(
        str(_attr(node, "parent_ref")).strip()
        for node in selected_checkpoint_nodes
        if str(_attr(node, "parent_ref")).strip() and ":attempt:" in str(_attr(node, "parent_ref")).strip()
    )
    attempt_refs.update(
        str(_attr(node, "attempt_id")).strip()
        for node in family_nodes.get("step", [])
        if _record_ref(node) in step_refs and str(_attr(node, "attempt_id")).strip()
    )

    decision_observation_nodes = [
        node
        for node in family_nodes.get("observation", [])
        if str(_attr(node, "step_id")).strip() in step_refs
        or str(_attr(node, "final_truth_record_id")).strip()
        or str(_attr(node, "observation_ref")).strip() in authoritative_result_refs
    ]
    selected.update(_node_ids_for_family(decision_observation_nodes))
    selected.update(_node_ids_for_refs("step", step_refs))
    selected.update(_node_ids_for_refs("attempt", attempt_refs))

    run_refs = {
        str(_attr(node, "run_id")).strip()
        for node in family_nodes.get("attempt", []) + final_truth_nodes + reconciliation_nodes
        if (
            _record_ref(node) in attempt_refs
            or node in final_truth_nodes
            or node in reconciliation_nodes
        )
        and str(_attr(node, "run_id")).strip()
    }
    selected.update(_node_ids_for_refs("run", run_refs))
    selected.update(
        _matching_operator_action_node_ids(
            operator_nodes=family_nodes.get("operator_action", []),
            run_refs=run_refs,
            transition_refs=attempt_refs | step_refs | checkpoint_refs,
            resource_refs=set(),
        )
    )
    return {node_id for node_id in selected if node_id in node_by_id}


def _resource_authority_path_node_ids(
    *,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    selected = _node_ids_for_family(family_nodes.get("reservation", []))
    selected.update(_node_ids_for_family(family_nodes.get("lease", [])))
    selected.update(_node_ids_for_family(family_nodes.get("resource", [])))
    selected.update(_node_ids_for_family(family_nodes.get("effect", [])))
    selected.update(_node_ids_for_family(family_nodes.get("observation", [])))
    selected.update(_node_ids_for_family(family_nodes.get("final_truth", [])))
    selected.update(_node_ids_for_family(family_nodes.get("reconciliation", [])))
    resource_refs = {_record_ref(node) for node in family_nodes.get("resource", [])}
    step_refs = {
        str(_attr(node, "step_id")).strip()
        for node in family_nodes.get("effect", []) + family_nodes.get("observation", [])
        if str(_attr(node, "step_id")).strip()
    }
    attempt_refs = {
        str(_attr(node, "attempt_id")).strip()
        for node in family_nodes.get("step", [])
        if _record_ref(node) in step_refs and str(_attr(node, "attempt_id")).strip()
    }
    run_refs = {
        str(_attr(node, "run_id")).strip()
        for node in family_nodes.get("attempt", []) + family_nodes.get("final_truth", [])
        if (_record_ref(node) in attempt_refs or node in family_nodes.get("final_truth", []))
        and str(_attr(node, "run_id")).strip()
    }
    selected.update(_node_ids_for_refs("step", step_refs))
    selected.update(_node_ids_for_refs("attempt", attempt_refs))
    selected.update(_node_ids_for_refs("run", run_refs))
    selected.update(
        _matching_operator_action_node_ids(
            operator_nodes=family_nodes.get("operator_action", []),
            run_refs=run_refs,
            transition_refs=attempt_refs | step_refs,
            resource_refs=resource_refs,
        )
    )
    return {node_id for node_id in selected if node_id in node_by_id}


def _closure_path_node_ids(
    *,
    node_by_id: dict[str, dict[str, Any]],
    family_nodes: dict[str, list[dict[str, Any]]],
) -> set[str]:
    final_truth_nodes = family_nodes.get("final_truth", [])
    if not final_truth_nodes:
        return set()
    selected = _node_ids_for_family(final_truth_nodes)
    run_refs = {
        str(_attr(node, "run_id")).strip() for node in final_truth_nodes if str(_attr(node, "run_id")).strip()
    }
    observation_refs = {
        str(_attr(node, "authoritative_result_ref")).strip()
        for node in final_truth_nodes
        if str(_attr(node, "authoritative_result_ref")).strip()
    }
    step_refs = {
        _record_ref(node)
        for node in family_nodes.get("step", [])
        if str(_attr(node, "output_ref")).strip() in observation_refs
    }
    attempt_refs = {
        str(_attr(node, "attempt_id")).strip()
        for node in family_nodes.get("step", [])
        if _record_ref(node) in step_refs and str(_attr(node, "attempt_id")).strip()
    }
    selected.update(_node_ids_for_refs("run", run_refs))
    selected.update(_node_ids_for_refs("observation", observation_refs))
    selected.update(_node_ids_for_refs("step", step_refs))
    selected.update(_node_ids_for_refs("attempt", attempt_refs))
    selected.update(
        _node_ids_for_family(
            [node for node in family_nodes.get("effect", []) if str(_attr(node, "step_id")).strip() in step_refs]
        )
    )
    selected.update(
        _node_ids_for_family(
            [node for node in family_nodes.get("observation", []) if str(_attr(node, "step_id")).strip() in step_refs]
        )
    )
    selected.update(
        _node_ids_for_family(
            [
                node
                for node in family_nodes.get("recovery_decision", [])
                if str(_attr(node, "failed_attempt_id")).strip() in attempt_refs
                or str(_attr(node, "new_attempt_id")).strip() in attempt_refs
                or str(_attr(node, "resumed_attempt_id")).strip() in attempt_refs
            ]
        )
    )
    selected.update(_node_ids_for_family(family_nodes.get("reconciliation", [])))
    selected.update(
        _matching_operator_action_node_ids(
            operator_nodes=family_nodes.get("operator_action", []),
            run_refs=run_refs,
            transition_refs=attempt_refs | step_refs,
            resource_refs=set(),
        )
    )
    return {node_id for node_id in selected if node_id in node_by_id}


def _matching_operator_action_node_ids(
    *,
    operator_nodes: list[dict[str, Any]],
    run_refs: set[str],
    transition_refs: set[str],
    resource_refs: set[str],
) -> set[str]:
    selected: set[str] = set()
    for node in operator_nodes:
        affected_transition_refs = {
            str(token).strip()
            for token in _attr(node, "affected_transition_refs", [])
            if str(token).strip()
        }
        affected_resource_refs = {
            str(token).strip()
            for token in _attr(node, "affected_resource_refs", [])
            if str(token).strip()
        }
        target_ref = str(_attr(node, "target_ref")).strip()
        if (
            target_ref in run_refs
            or bool(affected_transition_refs.intersection(transition_refs))
            or bool(affected_resource_refs.intersection(resource_refs))
        ):
            selected.add(str(node.get("id") or ""))
    return selected


def _nodes_by_family(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    families: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        family = str(node.get("family") or "").strip()
        families.setdefault(family, []).append(node)
    return families


def _node_ids_for_family(nodes: list[dict[str, Any]] | None) -> set[str]:
    return {str(node.get("id") or "") for node in (nodes or []) if str(node.get("id") or "").strip()}


def _node_ids_for_refs(family: str, refs: set[str]) -> set[str]:
    return {_node_id(family, ref) for ref in refs if ref}


def _node_id(family: str, record_ref: str) -> str:
    return f"{family}:{record_ref}" if str(record_ref).strip() else ""


def _record_ref(node: dict[str, Any]) -> str:
    node_id = str(node.get("id") or "").strip()
    return node_id.split(":", 1)[1] if ":" in node_id else ""


def _attr(node: dict[str, Any], key: str, default: Any = "") -> Any:
    attributes = node.get("attributes")
    if not isinstance(attributes, dict):
        return default
    return attributes.get(key, default)


def _mermaid_alias(*, view: str, node_id: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", f"{view}_{node_id}")
    return f"node_{token.strip('_') or 'unknown'}"


def _mermaid_label(node: dict[str, Any]) -> str:
    family = str(node.get("family") or "").strip()
    label = str(node.get("label") or node.get("id") or "").strip()
    return _escape_mermaid(f"[{family}] {label}")


def _escape_mermaid(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', "&quot;")


__all__ = [
    "build_run_evidence_graph_html",
    "build_run_evidence_graph_mermaid",
    "build_run_evidence_graph_views",
    "write_run_evidence_graph_html_artifact",
    "write_run_evidence_graph_mermaid_artifact",
    "write_run_evidence_graph_rendered_artifacts",
]
