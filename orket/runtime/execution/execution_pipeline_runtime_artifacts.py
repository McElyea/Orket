from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

from orket.core.cards_runtime_contract import normalize_scenario_truth_alignment, summarize_cards_runtime_issues
from orket.runtime.phase_c_runtime_truth import collect_phase_c_packet2_facts
from orket.utils import sanitize_name


class ExecutionPipelineRuntimeArtifactsMixin:
    if TYPE_CHECKING:
        workspace: Path
        async_cards: Any

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

        async def _record_packet2_facts(
            self,
            *,
            run_id: str,
            packet2_facts: dict[str, Any],
        ) -> None: ...

        async def _resolve_artifact_provenance_entries(self, *, run_id: str) -> list[dict[str, Any]]: ...

        async def _record_artifact_provenance_facts(
            self,
            *,
            run_id: str,
            artifact_provenance_facts: dict[str, Any],
        ) -> None: ...

    async def _resolve_packet1_artifacts(
        self,
        *,
        run_id: str,
        repair_entries: list[dict[str, Any]] | None = None,
        artifact_provenance_facts: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runtime_telemetry = await self._resolve_packet1_runtime_telemetry(run_id=run_id)
        repair_facts = self._build_packet1_repair_facts(repair_entries or [])
        packet1_facts = {
            **self._build_packet1_facts(intended_model=None, runtime_telemetry=runtime_telemetry),
            **repair_facts,
        }
        primary_work_artifact = self._select_primary_work_artifact_output(
            artifact_provenance_facts=artifact_provenance_facts
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
    ) -> dict[str, Any]:
        packet2_facts = await collect_phase_c_packet2_facts(
            workspace=self.workspace,
            run_id=run_id,
            cards_repo=self.async_cards,
            policy=phase_c_truth_policy,
            artifact_provenance_facts=artifact_provenance_facts,
        )
        packet2_facts.update(self._build_packet2_facts(repair_entries=repair_entries or []))
        if not packet2_facts:
            return {}
        await self._record_packet2_facts(run_id=run_id, packet2_facts=packet2_facts)
        return {"packet2_facts": packet2_facts}

    async def _resolve_artifact_provenance_artifacts(self, *, run_id: str) -> dict[str, Any]:
        entries = await self._resolve_artifact_provenance_entries(run_id=run_id)
        artifact_provenance_facts = self._build_artifact_provenance_facts(entries=entries)
        if not artifact_provenance_facts:
            return {}
        await self._record_artifact_provenance_facts(
            run_id=run_id,
            artifact_provenance_facts=artifact_provenance_facts,
        )
        return {"artifact_provenance_facts": artifact_provenance_facts}

    async def _resolve_packet1_runtime_telemetry(self, *, run_id: str) -> dict[str, Any]:
        candidate_paths = await asyncio.to_thread(self._packet1_model_response_paths, run_id)
        selected: dict[str, Any] = {}
        for path in candidate_paths:
            try:
                async with aiofiles.open(path, encoding="utf-8") as handle:
                    payload = json.loads(await handle.read())
            except (OSError, ValueError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            selected = payload
        return selected

    async def _resolve_packet2_repair_entries(self, *, run_id: str) -> list[dict[str, Any]]:
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return []
        repairs_by_id: dict[str, dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("event") or "").strip() != "turn_corrective_reprompt":
                        continue
                    raw_data = payload.get("data")
                    data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
                    if str(data.get("session_id") or "").strip() != str(run_id):
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
                        if issue_id
                        else f"repair:turn:{turn_index}:corrective_reprompt"
                    )
                    existing = repairs_by_id.get(repair_id)
                    if existing is None:
                        entry: dict[str, Any] = {
                            "repair_id": repair_id,
                            "turn_index": turn_index,
                            "source_event": "turn_corrective_reprompt",
                            "strategy": "corrective_reprompt",
                            "reasons": reasons,
                            "material_change": True,
                        }
                        if issue_id:
                            entry["issue_id"] = issue_id
                        repairs_by_id[repair_id] = entry
                        continue
                    existing["reasons"] = sorted(set(list(existing.get("reasons") or []) + reasons))
        except OSError:
            return []
        return [repairs_by_id[key] for key in sorted(repairs_by_id)]

    async def _resolve_cards_runtime_artifacts(
        self,
        *,
        artifacts: dict[str, Any],
        run_id: str,
        session_status: str,
        failure_reason: str | None,
    ) -> dict[str, Any]:
        if not self._cards_runtime_resolution_applicable(artifacts):
            return {}
        existing_summary = artifacts.get("cards_runtime_facts")
        if isinstance(existing_summary, dict) and existing_summary:
            return {}
        log_path = self.workspace / "orket.log"
        if not log_path.exists():
            return self._cards_runtime_resolution_artifact("log_missing")
        issues: dict[str, dict[str, Any]] = {}
        try:
            async with aiofiles.open(log_path, encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("event") or "").strip() not in {
                        "turn_start",
                        "turn_complete",
                        "turn_failed",
                        "odr_prebuild_completed",
                        "odr_prebuild_failed",
                    }:
                        continue
                    raw_data = payload.get("data")
                    data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, dict) else {}
                    if str(data.get("session_id") or "").strip() != str(run_id):
                        continue
                    issue_id = str(data.get("issue_id") or "").strip()
                    if not issue_id:
                        continue
                    row = issues.setdefault(issue_id, {"issue_id": issue_id})
                    for key in (
                        "execution_profile",
                        "builder_seat_choice",
                        "reviewer_seat_choice",
                        "profile_traits",
                        "seat_coercion",
                        "artifact_contract",
                        "scenario_truth",
                        "odr_active",
                        "audit_mode",
                        "odr_stop_reason",
                        "odr_valid",
                        "odr_pending_decisions",
                        "odr_artifact_path",
                        "last_valid_round_index",
                        "last_emitted_round_index",
                    ):
                        if key not in data:
                            continue
                        value = data.get(key)
                        if value is None:
                            continue
                        if isinstance(value, str) and not value.strip():
                            continue
                        if isinstance(value, (list, dict)) and not value:
                            continue
                        row[key] = value
        except OSError as exc:
            return self._cards_runtime_resolution_artifact("resolution_failed", error=exc)
        if not issues:
            return self._cards_runtime_resolution_artifact("no_events_found")
        summary = summarize_cards_runtime_issues(list(issues.values()))
        if not summary:
            return self._cards_runtime_resolution_artifact("no_events_found")
        summary["resolution_state"] = "resolved"
        summary["stop_reason"] = self._resolve_cards_stop_reason(
            session_status=session_status,
            failure_reason=failure_reason,
        )
        scenario_truth_alignment = normalize_scenario_truth_alignment(
            scenario_truth=summary.get("scenario_truth"),
            observed_terminal_status=session_status,
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

    def _packet1_model_response_paths(self, run_id: str) -> list[Path]:
        observability_root = self.workspace / "observability" / sanitize_name(run_id)
        if not observability_root.exists():
            return []
        return sorted(observability_root.rglob("model_response_raw.json"))
