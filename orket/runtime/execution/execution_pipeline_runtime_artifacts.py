from __future__ import annotations

import json
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.core.cards_runtime_contract import normalize_scenario_truth_alignment, summarize_cards_runtime_issues
from orket.runtime.phase_c_runtime_truth import collect_phase_c_packet2_facts
from orket.utils import sanitize_name


class ExecutionPipelineRuntimeArtifactsMixin:
    if TYPE_CHECKING:
        def _build_packet1_facts(
            self,
            *,
            intended_model: str | None,
            runtime_telemetry: dict[str, Any] | None = None,
        ) -> dict[str, Any]: ...

        def _select_primary_work_artifact_output(
            self,
            *,
            artifact_provenance_facts: dict[str, Any] | None = None,
        ) -> dict[str, str]: ...

        async def _record_packet2_facts_at(
            self,
            *,
            run_id: str,
            packet2_facts: dict[str, Any],
            ledger: Any,
        ) -> None: ...

        async def _resolve_artifact_provenance_entries(
            self, *, run_id: str, workspace: Path,
        ) -> list[dict[str, Any]]: ...

        async def _record_artifact_provenance_facts_at(
            self,
            *,
            run_id: str,
            artifact_provenance_facts: dict[str, Any],
            ledger: Any,
        ) -> None: ...

    async def _resolve_packet1_artifacts(
        self,
        *,
        run_id: str,
        repair_entries: list[dict[str, Any]] | None = None,
        artifact_provenance_facts: dict[str, Any] | None = None,
        workspace: Path,
    ) -> dict[str, Any]:
        captured_workspace, = capture_file_roots([workspace])
        captured_repairs = deepcopy(repair_entries or [])
        captured_provenance = deepcopy(artifact_provenance_facts)
        runtime_telemetry = await self._resolve_packet1_runtime_telemetry_at(
            run_id=run_id, workspace=captured_workspace)
        repair_facts = self._build_packet1_repair_facts(captured_repairs)
        packet1_facts = {
            **self._build_packet1_facts(intended_model=None, runtime_telemetry=runtime_telemetry),
            **repair_facts,
        }
        primary_work_artifact = self._select_primary_work_artifact_output(
            artifact_provenance_facts=captured_provenance
        )
        if primary_work_artifact:
            packet1_facts["primary_work_artifact_output"] = primary_work_artifact
        return {"packet1_facts": packet1_facts}

    async def _resolve_packet2_artifacts(
        self,
        *,
        run_id: str,
        repair_entries: list[dict[str, Any]] | None = None,
        artifact_provenance_facts: dict[str, Any] | None = None,
        phase_c_truth_policy: dict[str, Any] | None = None,
        workspace: Path,
        cards_repo: Any,
        ledger: Any,
    ) -> dict[str, Any]:
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        captured_repairs = deepcopy(repair_entries or [])
        captured_provenance = deepcopy(artifact_provenance_facts)
        captured_policy = deepcopy(phase_c_truth_policy)
        packet2_facts = await collect_phase_c_packet2_facts(
            workspace=captured_workspace,
            run_id=captured_run_id,
            cards_repo=cards_repo,
            policy=captured_policy,
            artifact_provenance_facts=captured_provenance,
        )
        packet2_facts.update(self._build_packet2_facts(repair_entries=captured_repairs))
        if not packet2_facts:
            return {}
        await self._record_packet2_facts_at(
            run_id=captured_run_id, packet2_facts=packet2_facts, ledger=ledger)
        return {"packet2_facts": packet2_facts}

    async def _resolve_artifact_provenance_artifacts(
        self, *, run_id: str, workspace: Path, ledger: Any,
    ) -> dict[str, Any]:
        captured_workspace, = capture_file_roots([workspace])
        entries = await self._resolve_artifact_provenance_entries(
            run_id=run_id, workspace=captured_workspace)
        artifact_provenance_facts = self._build_artifact_provenance_facts(entries=entries)
        if not artifact_provenance_facts:
            return {}
        await self._record_artifact_provenance_facts_at(
            run_id=run_id,
            artifact_provenance_facts=artifact_provenance_facts,
            ledger=ledger,
        )
        return {"artifact_provenance_facts": artifact_provenance_facts}

    async def _resolve_packet1_runtime_telemetry_at(self, *, run_id: str, workspace: Path) -> dict[str, Any]:
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        candidate_paths = await run_owned_thread(
            partial(self._packet1_model_response_paths_at, captured_run_id, workspace=captured_workspace),
            label="packet1-response-discovery",
        )
        selected: dict[str, Any] = {}
        for path in candidate_paths:
            payload = await run_owned_io(
                lambda path=path: _read_optional_json(path), label="packet1-response-read",
                preserve_failure=True,
            )
            if not isinstance(payload, dict):
                continue
            selected = payload
        return selected

    async def _resolve_packet2_repair_entries_at(self, *, run_id: str, workspace: Path) -> list[dict[str, Any]]:
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        log_path = captured_workspace / "orket.log"
        if not await run_owned_thread(log_path.exists, label="packet2-repair-log-exists"):
            return []
        repairs_by_id: dict[str, dict[str, Any]] = {}
        rows, _ = await run_owned_io(
            lambda: _read_optional_json_lines(log_path),
            label="packet2-repair-log-read",
            preserve_failure=True,
        )
        for payload in rows:
            if str(payload.get("event") or "").strip() != "turn_corrective_reprompt":
                continue
            raw_data = payload.get("data")
            data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
            if str(data.get("session_id") or "").strip() != captured_run_id:
                continue
            reasons = sorted(
                {str(reason).strip() for reason in (data.get("contract_reasons") or []) if str(reason).strip()}
            )
            if not reasons:
                continue
            issue_id = str(data.get("issue_id") or "").strip()
            turn_index_raw = data.get("turn_index")
            turn_index = max(0, int(turn_index_raw)) if isinstance(turn_index_raw, int) else 0
            repair_id = (
                f"repair:{issue_id}:{turn_index}:corrective_reprompt"
                if issue_id else f"repair:turn:{turn_index}:corrective_reprompt"
            )
            existing = repairs_by_id.get(repair_id)
            if existing is None:
                entry: dict[str, Any] = {
                    "repair_id": repair_id, "turn_index": turn_index,
                    "source_event": "turn_corrective_reprompt", "strategy": "corrective_reprompt",
                    "reasons": reasons, "material_change": True,
                }
                if issue_id:
                    entry["issue_id"] = issue_id
                repairs_by_id[repair_id] = entry
                continue
            existing["reasons"] = sorted(set(list(existing.get("reasons") or []) + reasons))
        return [repairs_by_id[key] for key in sorted(repairs_by_id)]

    async def _resolve_cards_runtime_artifacts_at(
        self, *, artifacts: dict[str, Any], run_id: str, session_status: str,
        failure_reason: str | None, workspace: Path,
    ) -> dict[str, Any]:
        if not self._cards_runtime_resolution_applicable(artifacts):
            return {}
        existing_summary = artifacts.get("cards_runtime_facts")
        if isinstance(existing_summary, dict) and existing_summary:
            return {}
        captured_workspace, = capture_file_roots([workspace])
        captured_run_id = str(run_id)
        captured_status = str(session_status)
        captured_failure = None if failure_reason is None else str(failure_reason)
        log_path = captured_workspace / "orket.log"
        if not await run_owned_thread(log_path.exists, label="cards-runtime-log-exists"):
            return self._cards_runtime_resolution_artifact("log_missing")
        issues: dict[str, dict[str, Any]] = {}
        rows, read_error = await run_owned_io(
            lambda: _read_optional_json_lines(log_path), label="cards-runtime-log-read",
            preserve_failure=True,
        )
        if read_error is not None:
            return self._cards_runtime_resolution_artifact("resolution_failed", error=read_error)
        for payload in rows:
            if str(payload.get("event") or "").strip() not in {
                "turn_start", "turn_complete", "turn_failed", "odr_prebuild_completed", "odr_prebuild_failed",
            }:
                continue
            raw_data = payload.get("data")
            data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
            if str(data.get("session_id") or "").strip() != captured_run_id:
                continue
            issue_id = str(data.get("issue_id") or "").strip()
            if not issue_id:
                continue
            row = issues.setdefault(issue_id, {"issue_id": issue_id})
            for key in (
                "execution_profile", "builder_seat_choice", "reviewer_seat_choice", "profile_traits",
                "seat_coercion", "artifact_contract", "scenario_truth", "odr_active", "audit_mode",
                "odr_stop_reason", "odr_valid", "odr_pending_decisions", "odr_artifact_path",
                "last_valid_round_index", "last_emitted_round_index",
            ):
                value = data.get(key)
                if key not in data or value is None or (isinstance(value, str) and not value.strip()):
                    continue
                if isinstance(value, (list, dict)) and not value:
                    continue
                row[key] = value
        if not issues:
            return self._cards_runtime_resolution_artifact("no_events_found")
        summary = summarize_cards_runtime_issues(list(issues.values()))
        if not summary:
            return self._cards_runtime_resolution_artifact("no_events_found")
        summary["resolution_state"] = "resolved"
        summary["stop_reason"] = self._resolve_cards_stop_reason(
            session_status=captured_status,
            failure_reason=captured_failure,
        )
        scenario_truth_alignment = normalize_scenario_truth_alignment(
            scenario_truth=summary.get("scenario_truth"),
            observed_terminal_status=captured_status,
        )
        if scenario_truth_alignment:
            summary["scenario_truth_alignment"] = scenario_truth_alignment
        return {"cards_runtime_facts": summary}

    @staticmethod
    def _cards_runtime_resolution_applicable(artifacts: dict[str, Any]) -> bool:
        run_identity = artifacts.get("run_identity")
        workload = str(run_identity.get("workload") or "").strip().lower() if isinstance(run_identity, dict) else ""
        control_plane_run = artifacts.get("control_plane_run_record")
        workload_id = (
            str(control_plane_run.get("workload_id") or "").strip().lower()
            if isinstance(control_plane_run, dict)
            else ""
        )
        return workload.startswith("cards") or workload_id.startswith("cards")

    @staticmethod
    def _cards_runtime_resolution_artifact(
        resolution_state: str,
        *,
        error: Exception | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"resolution_state": str(resolution_state).strip()}
        if error is not None:
            payload["resolution_error"] = {
                "error_type": type(error).__name__,
                "error": str(error),
            }
        return {"cards_runtime_facts": payload}

    @staticmethod
    def _resolve_cards_stop_reason(*, session_status: str, failure_reason: str | None) -> str:
        explicit_failure = str(failure_reason or "").strip()
        if explicit_failure:
            return explicit_failure
        token = str(session_status or "").strip().lower()
        if token == "done":
            return "completed"
        if token == "incomplete":
            return "open_issues_remaining"
        if token == "terminal_failure":
            return "terminal_failure"
        if token == "failed":
            return "failed"
        return token or "unknown"

    def _build_packet1_repair_facts(self, repair_entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not repair_entries:
            return {}
        repair_reasons = sorted(
            {
                str(reason).strip()
                for entry in repair_entries
                for reason in list(entry.get("reasons") or [])
                if str(reason).strip()
            }
        )
        repair_strategies = sorted(
            {
                str(entry.get("strategy") or "").strip()
                for entry in repair_entries
                if str(entry.get("strategy") or "").strip()
            }
        )
        return {
            "repair_occurred": True,
            "repair_material_change": True,
            "repair_strategy": repair_strategies[0] if len(repair_strategies) == 1 else "multiple_repair_strategies",
            "repair_reasons": repair_reasons,
        }

    def _build_packet2_facts(self, *, repair_entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not repair_entries:
            return {}
        return {
            "repair_entries": [dict(entry) for entry in repair_entries],
            "final_disposition": "accepted_with_repair",
        }

    def _build_artifact_provenance_facts(self, *, entries: list[dict[str, Any]]) -> dict[str, Any]:
        if not entries:
            return {}
        return {
            "artifacts": [dict(entry) for entry in entries],
        }

    @staticmethod
    def _packet1_model_response_paths_at(run_id: str, *, workspace: Path) -> list[Path]:
        observability_root = workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("model_response_raw.json"))


async def _read_optional_json(path: Path) -> dict[str, Any] | None:
    try:
        async with aiofiles.open(path, encoding="utf-8") as handle:
            payload = json.loads(await handle.read())
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


async def _read_optional_json_lines(path: Path) -> tuple[list[dict[str, Any]], OSError | None]:
    rows: list[dict[str, Any]] = []
    try:
        async with aiofiles.open(path, encoding="utf-8") as handle:
            async for line in handle:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError as exc:
        return [], exc
    return rows, None
