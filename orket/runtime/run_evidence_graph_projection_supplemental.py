from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import aiofiles

from orket.application.services.run_ledger_summary_projection import validated_run_ledger_record_projection
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.run_ledger_projection import project_run_ledger_record
from orket.runtime.run_evidence_graph_projection_support import (
    PrimaryLineageContext,
    issue,
    source_id,
    source_summary,
)
from orket.runtime.run_summary import validate_run_summary_payload


@dataclass(slots=True)
class SupplementalProjection:
    source_summaries: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    run_annotations: dict[str, Any] = field(default_factory=dict)
    attempt_annotations_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    step_annotations_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)


async def load_supplemental_projection(
    *,
    root: Path,
    session_root: Path,
    session_id: str,
    run_id: str,
    context: PrimaryLineageContext,
) -> SupplementalProjection:
    projection = SupplementalProjection()
    _merge_projection(
        projection,
        await _load_run_summary_annotation(
            session_root=session_root,
            session_id=session_id,
            run_id=run_id,
            context=context,
        ),
    )
    _merge_projection(
        projection,
        await _load_run_ledger_annotation(
            root=root,
            session_id=session_id,
            run_id=run_id,
            context=context,
        ),
    )
    _merge_projection(
        projection,
        await _load_runtime_event_annotations(
            root=root,
            session_id=session_id,
            run_id=run_id,
            context=context,
        ),
    )
    return projection


def _merge_projection(target: SupplementalProjection, incoming: SupplementalProjection) -> None:
    target.source_summaries.extend(incoming.source_summaries)
    target.issues.extend(incoming.issues)
    target.run_annotations.update(incoming.run_annotations)
    for attempt_id, annotations in incoming.attempt_annotations_by_id.items():
        target.attempt_annotations_by_id.setdefault(attempt_id, {}).update(annotations)
    for step_id, annotations in incoming.step_annotations_by_id.items():
        target.step_annotations_by_id.setdefault(step_id, {}).update(annotations)


async def _load_run_summary_annotation(
    *,
    session_root: Path,
    session_id: str,
    run_id: str,
    context: PrimaryLineageContext,
) -> SupplementalProjection:
    projection = SupplementalProjection()
    run_summary_path = session_root / "run_summary.json"
    if not await asyncio.to_thread(run_summary_path.exists):
        return projection

    path_ref = f"runs/{session_id}/run_summary.json"
    summary_source_id = source_id("run_summary.json", path_ref)
    try:
        async with aiofiles.open(run_summary_path, mode="r", encoding="utf-8") as handle:
            payload = json.loads(await handle.read())
        if not isinstance(payload, dict):
            raise ValueError("run_summary_payload_not_object")
        validate_run_summary_payload(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        projection.source_summaries.append(
            source_summary(
                source_id=summary_source_id,
                authority_level="supplemental",
                source_kind="run_summary.json",
                status="contradictory",
                source_ref=path_ref,
                detail=f"validated supplemental run_summary.json annotation is unavailable: {exc}",
            )
        )
        projection.issues.append(
            issue(
                code="supplemental_run_summary_invalid",
                detail=f"supplemental run_summary.json is present but invalid for run {run_id}",
                source_id=summary_source_id,
            )
        )
        return projection

    control_plane = payload.get("control_plane")
    control_plane_run_id = ""
    if isinstance(control_plane, dict):
        control_plane_run_id = str(control_plane.get("run_id") or "").strip()
    top_level_run_id = str(payload.get("run_id") or "").strip()
    if top_level_run_id != run_id and control_plane_run_id != run_id:
        return projection

    projection.source_summaries.append(
        source_summary(
            source_id=summary_source_id,
            authority_level="supplemental",
            source_kind="run_summary.json",
            status="present",
            source_ref=path_ref,
        )
    )
    projection.run_annotations["supplemental_run_summary_ref"] = path_ref
    if not isinstance(control_plane, dict) or control_plane_run_id != run_id:
        return projection

    attempt_id = str(control_plane.get("attempt_id") or control_plane.get("current_attempt_id") or "").strip()
    if attempt_id and attempt_id in context.attempts_by_id:
        projection.attempt_annotations_by_id.setdefault(attempt_id, {})[
            "supplemental_run_summary_selected_attempt"
        ] = True

    step_id = str(control_plane.get("step_id") or "").strip()
    if step_id and step_id in context.steps_by_id:
        projection.step_annotations_by_id.setdefault(step_id, {})["supplemental_run_summary_selected_step"] = True
    return projection


async def _load_runtime_event_annotations(
    *,
    root: Path,
    session_id: str,
    run_id: str,
    context: PrimaryLineageContext,
) -> SupplementalProjection:
    projection = SupplementalProjection()
    events_repo = AsyncProtocolRunLedgerRepository(root)
    events = await events_repo.list_events(session_id)
    if not events:
        return projection

    step_event_sequences: dict[str, list[int]] = {}
    attempt_event_sequences: dict[str, list[int]] = {}
    contradictions: list[str] = []

    for event in events:
        manifest = event.get("tool_invocation_manifest")
        if not isinstance(manifest, dict):
            continue
        if str(manifest.get("control_plane_run_id") or "").strip() != run_id:
            continue
        event_seq = _event_sequence(event)
        if event_seq is None:
            continue
        attempt_id = str(manifest.get("control_plane_attempt_id") or "").strip()
        step_id = str(manifest.get("control_plane_step_id") or "").strip()
        if attempt_id and attempt_id not in context.attempts_by_id:
            contradictions.append(f"event_seq {event_seq} references missing attempt {attempt_id}")
            continue
        if step_id:
            step = context.steps_by_id.get(step_id)
            if step is None:
                contradictions.append(f"event_seq {event_seq} references missing step {step_id}")
                continue
            if attempt_id and step.attempt_id != attempt_id:
                contradictions.append(
                    f"event_seq {event_seq} links step {step_id} to contradictory attempt {attempt_id}"
                )
                continue
            step_event_sequences.setdefault(step_id, []).append(event_seq)
            attempt_event_sequences.setdefault(step.attempt_id, []).append(event_seq)
            continue
        if attempt_id:
            attempt_event_sequences.setdefault(attempt_id, []).append(event_seq)

    aligned_event_count = sum(len(sequences) for sequences in step_event_sequences.values())
    if not aligned_event_count and not contradictions:
        return projection

    path_ref = f"runs/{session_id}/events.log"
    events_source_id = source_id("events.log", path_ref)
    projection.source_summaries.append(
        source_summary(
            source_id=events_source_id,
            authority_level="supplemental",
            source_kind="events.log",
            status="present" if aligned_event_count else "contradictory",
            source_ref=path_ref,
            attributes={
                "aligned_event_count": aligned_event_count,
                "contradiction_count": len(contradictions),
            },
        )
    )
    projection.run_annotations["supplemental_runtime_events_ref"] = path_ref
    projection.run_annotations["supplemental_runtime_aligned_event_count"] = aligned_event_count

    for attempt_id, sequences in attempt_event_sequences.items():
        projection.attempt_annotations_by_id.setdefault(attempt_id, {}).update(
            {
                "supplemental_runtime_event_seq_range": [min(sequences), max(sequences)],
                "supplemental_runtime_event_count": len(sequences),
            }
        )

    ordered_steps = sorted(step_event_sequences.items(), key=lambda item: (min(item[1]), item[0]))
    for index, (step_id, sequences) in enumerate(ordered_steps, start=1):
        projection.step_annotations_by_id.setdefault(step_id, {}).update(
            {
                "supplemental_runtime_event_seq_range": [min(sequences), max(sequences)],
                "supplemental_runtime_event_count": len(sequences),
                "supplemental_runtime_order_index": index,
                "supplemental_runtime_order_basis": "events.log/tool_invocation_manifest.control_plane_step_id",
            }
        )

    if contradictions:
        projection.issues.append(
            issue(
                code="supplemental_runtime_event_alignment_invalid",
                detail=f"runtime event alignment drifted for run {run_id}: {'; '.join(contradictions[:3])}",
                source_id=events_source_id,
            )
        )
    return projection


async def _load_run_ledger_annotation(
    *,
    root: Path,
    session_id: str,
    run_id: str,
    context: PrimaryLineageContext,
) -> SupplementalProjection:
    projection = SupplementalProjection()
    run_ledger = await AsyncProtocolRunLedgerRepository(root).get_run(session_id)
    if run_ledger is None:
        return projection

    projected_record, invalid_fields = project_run_ledger_record(run_ledger)
    if projected_record is None:
        return projection

    path_ref = f"runs/{session_id}/events.log#get_run.summary_json"
    ledger_source_id = source_id("run_ledger.summary_json", path_ref)
    validated_projection = validated_run_ledger_record_projection(run_ledger) or {}
    raw_summary = projected_record.get("summary_json") or {}
    validated_summary = validated_projection.get("summary_json") or {}
    if "summary_json" in invalid_fields or (raw_summary and not validated_summary):
        projection.source_summaries.append(
            source_summary(
                source_id=ledger_source_id,
                authority_level="supplemental",
                source_kind="run_ledger.summary_json",
                status="contradictory",
                source_ref=path_ref,
                detail=f"validated supplemental run-ledger summary is unavailable for run {run_id}",
            )
        )
        projection.issues.append(
            issue(
                code="supplemental_run_ledger_summary_invalid",
                detail=f"supplemental run-ledger summary is present but invalid for run {run_id}",
                source_id=ledger_source_id,
            )
        )
        return projection

    if not validated_summary:
        return projection

    summary_run_id = str(validated_summary.get("run_id") or "").strip()
    control_plane = validated_summary.get("control_plane")
    control_plane_run_id = str(control_plane.get("run_id") or "").strip() if isinstance(control_plane, dict) else ""
    if summary_run_id != run_id and control_plane_run_id != run_id:
        return projection

    started_event_seq = _positive_int(run_ledger.get("started_event_seq"))
    ended_event_seq = _positive_int(run_ledger.get("ended_event_seq"))
    projection.source_summaries.append(
        source_summary(
            source_id=ledger_source_id,
            authority_level="supplemental",
            source_kind="run_ledger.summary_json",
            status="present",
            source_ref=path_ref,
            attributes={
                "started_event_seq": started_event_seq,
                "ended_event_seq": ended_event_seq,
            },
        )
    )
    projection.run_annotations["supplemental_run_ledger_summary_ref"] = path_ref
    if started_event_seq is not None:
        projection.run_annotations["supplemental_run_ledger_started_event_seq"] = started_event_seq
    if ended_event_seq is not None:
        projection.run_annotations["supplemental_run_ledger_ended_event_seq"] = ended_event_seq

    if not isinstance(control_plane, dict) or control_plane_run_id != run_id:
        return projection

    attempt_id = str(control_plane.get("attempt_id") or control_plane.get("current_attempt_id") or "").strip()
    if attempt_id and attempt_id in context.attempts_by_id:
        projection.attempt_annotations_by_id.setdefault(attempt_id, {})[
            "supplemental_run_ledger_selected_attempt"
        ] = True

    step_id = str(control_plane.get("step_id") or "").strip()
    if step_id and step_id in context.steps_by_id:
        projection.step_annotations_by_id.setdefault(step_id, {})["supplemental_run_ledger_selected_step"] = True
    return projection


def _event_sequence(event: dict[str, Any]) -> int | None:
    try:
        value = int(event.get("event_seq") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _positive_int(value: Any) -> int | None:
    try:
        normalized = int(value or 0)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


__all__ = ["SupplementalProjection", "load_supplemental_projection"]
