from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from orket.logging import log_event
from orket.runtime.run_start_artifacts import validate_run_identity_projection
from orket.runtime.run_summary import (
    PACKET1_MISSING_TOKEN,
    build_degraded_run_summary_payload,
    generate_run_summary_for_finalize,
    write_run_summary_artifact,
)
from orket.runtime.run_summary_artifact_provenance import normalize_artifact_provenance_facts
from orket.utils import sanitize_name

_RUN_SUMMARY_RUN_IDENTITY_ERROR_PREFIX = "run_summary_run_identity_"
_TRANSIENT_RUN_IDENTITY_ARTIFACT_KEYS = ("run_identity", "run_identity_path")


def _is_run_summary_run_identity_error(exc: Exception) -> bool:
    return str(exc).strip().startswith(_RUN_SUMMARY_RUN_IDENTITY_ERROR_PREFIX)


def _strip_transient_run_identity_artifacts(artifacts: dict[str, Any]) -> None:
    for key in _TRANSIENT_RUN_IDENTITY_ARTIFACT_KEYS:
        artifacts.pop(key, None)


class ExecutionPipelineRunSummaryMixin:
    if TYPE_CHECKING:
        workspace: Path
        artifact_exporter: Any

        async def _resolve_packet2_repair_entries(self, *, run_id: str) -> list[dict[str, Any]]: ...

        async def _resolve_artifact_provenance_artifacts(self, *, run_id: str) -> dict[str, Any]: ...

        async def _resolve_cards_runtime_artifacts(
            self,
            *,
            run_id: str,
            session_status: str,
            failure_reason: str | None,
        ) -> dict[str, Any]: ...

        async def _resolve_packet1_artifacts(
            self,
            *,
            run_id: str,
            repair_entries: list[dict[str, Any]] | None = None,
            artifact_provenance_facts: dict[str, Any] | None = None,
        ) -> dict[str, Any]: ...

        async def _resolve_packet2_artifacts(
            self,
            *,
            run_id: str,
            repair_entries: list[dict[str, Any]] | None = None,
            artifact_provenance_facts: dict[str, Any] | None = None,
            phase_c_truth_policy: dict[str, Any] | None = None,
        ) -> dict[str, Any]: ...

        async def _record_packet1_emission_failure(
            self,
            *,
            run_id: str,
            stage: str,
            error_type: str,
            error: str,
        ) -> None: ...

    def _run_artifact_refs(self, run_id: str) -> dict[str, str]:
        return {
            "workspace": str(self.workspace),
            "orket_log": str(self.workspace / "orket.log"),
            "observability_root": str(self.workspace / "observability" / sanitize_name(run_id)),
            "agent_output_root": str(self.workspace / "agent_output"),
        }

    def _build_packet1_facts(
        self,
        *,
        intended_model: str | None,
        runtime_telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = (
            str(os.environ.get("ORKET_LLM_PROVIDER") or os.environ.get("ORKET_MODEL_PROVIDER") or "ollama")
            .strip()
            .lower()
        )
        configured_profile = self._normalize_packet1_token(os.environ.get("ORKET_LOCAL_PROMPTING_PROFILE_ID"))
        fallback_profile = self._normalize_packet1_token(os.environ.get("ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID"))
        telemetry = dict(runtime_telemetry or {})
        intended_model_token = self._normalize_packet1_token(intended_model) or self._normalize_packet1_token(
            telemetry.get("requested_model")
        )
        actual_provider = (
            str(
                telemetry.get("provider_backend")
                or telemetry.get("provider_name")
                or telemetry.get("provider")
                or provider
            )
            .strip()
            .lower()
            or provider
        )
        actual_model = (
            self._normalize_packet1_token(telemetry.get("model")) or intended_model_token or PACKET1_MISSING_TOKEN
        )
        actual_profile = self._normalize_packet1_token(telemetry.get("profile_id")) or "default"
        resolution_path = str(telemetry.get("profile_resolution_path") or "").strip().lower()
        fallback_detected = resolution_path == "fallback"
        retry_count = telemetry.get("retries")
        retry_occurred = isinstance(retry_count, int) and retry_count > 0
        intended_profile = configured_profile or (fallback_profile if fallback_detected else "") or actual_profile
        return {
            "intended_provider": provider,
            "intended_model": intended_model_token or PACKET1_MISSING_TOKEN,
            "intended_profile": intended_profile or PACKET1_MISSING_TOKEN,
            "actual_provider": actual_provider,
            "actual_model": actual_model,
            "actual_profile": actual_profile,
            "path_mismatch": False,
            "mismatch_reason": "none",
            "retry_occurred": retry_occurred,
            "repair_occurred": False,
            "fallback_occurred": fallback_detected,
            "fallback_path_detected": fallback_detected,
            "machine_mismatch_indicator": True,
            "output_presented_as_normal_success": True,
            "execution_profile": "fallback" if fallback_detected else "normal",
        }

    @staticmethod
    def _normalize_packet1_token(value: Any) -> str:
        if value is None:
            return ""
        raw = str(value).strip()
        if not raw or raw.lower() in {"none", "unknown"}:
            return ""
        return raw

    def _merge_packet1_facts(
        self,
        existing_packet1_facts: dict[str, Any],
        updated_packet1_facts: dict[str, Any],
    ) -> dict[str, Any]:
        merged = dict(existing_packet1_facts)
        for key, value in updated_packet1_facts.items():
            if key in {
                "intended_provider",
                "intended_model",
                "intended_profile",
                "actual_provider",
                "actual_model",
                "actual_profile",
            } and str(value).strip() == PACKET1_MISSING_TOKEN and self._normalize_packet1_token(
                existing_packet1_facts.get(key)
            ):
                continue
            merged[key] = value
        return merged

    def _select_primary_work_artifact_output(
        self,
        *,
        artifact_provenance_facts: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        facts = normalize_artifact_provenance_facts(artifact_provenance_facts)
        entries = list(facts.get("artifacts") or [])
        entries = [
            entry for entry in entries if str(entry.get("artifact_type") or "").strip() != "source_attribution_receipt"
        ]
        if not entries:
            return {}
        selected = max(
            entries,
            key=lambda entry: (
                int(entry.get("turn_index") or 0),
                str(entry.get("produced_at") or ""),
                str(entry.get("artifact_path") or ""),
            ),
        )
        artifact_path = str(selected.get("artifact_path") or "").strip()
        if not artifact_path:
            return {}
        output: dict[str, str] = {"id": artifact_path, "kind": "artifact"}
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(selected.get(field) or "").strip()
            if token:
                output[field] = token
        return output

    async def _export_run_artifacts(
        self,
        *,
        run_id: str,
        run_type: str,
        run_name: str,
        build_id: str,
        session_status: str,
        summary: dict[str, Any],
        failure_class: str | None = None,
        failure_reason: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            exported = await self.artifact_exporter.export_run(
                run_id=run_id,
                run_type=run_type,
                run_name=run_name,
                build_id=build_id,
                session_status=session_status,
                summary=summary,
                failure_class=failure_class,
                failure_reason=failure_reason,
            )
            if isinstance(exported, dict) and exported:
                log_event(
                    "run_artifacts_exported",
                    {
                        "run_id": run_id,
                        "provider": exported.get("provider"),
                        "repo": f"{exported.get('owner')}/{exported.get('repo')}",
                        "branch": exported.get("branch"),
                        "path": exported.get("path"),
                        "commit": exported.get("commit"),
                    },
                    workspace=self.workspace,
                )
                return dict(exported)
            return None
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            log_event(
                "run_artifact_export_failed",
                {
                    "run_id": run_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                workspace=self.workspace,
            )
            return None

    async def _materialize_run_summary(
        self,
        *,
        run_id: str,
        session_status: str,
        failure_reason: str | None,
        artifacts: dict[str, Any],
        finalized_at: str,
        phase_c_truth_policy: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        resolved_artifacts = dict(artifacts)
        repair_entries = await self._resolve_packet2_repair_entries(run_id=run_id)
        artifact_provenance_artifacts = await self._resolve_artifact_provenance_artifacts(run_id=run_id)
        cards_runtime_artifacts = await self._resolve_cards_runtime_artifacts(
            run_id=run_id,
            session_status=session_status,
            failure_reason=failure_reason,
        )
        packet1_artifacts = await self._resolve_packet1_artifacts(
            run_id=run_id,
            repair_entries=repair_entries,
            artifact_provenance_facts=artifact_provenance_artifacts.get("artifact_provenance_facts"),
        )
        packet2_artifacts = await self._resolve_packet2_artifacts(
            run_id=run_id,
            repair_entries=repair_entries,
            artifact_provenance_facts=artifact_provenance_artifacts.get("artifact_provenance_facts"),
            phase_c_truth_policy=phase_c_truth_policy,
        )
        existing_packet1_facts = dict(resolved_artifacts.get("packet1_facts") or {})
        merged_packet1_facts = self._merge_packet1_facts(
            existing_packet1_facts,
            dict(packet1_artifacts.get("packet1_facts") or {}),
        )
        if merged_packet1_facts:
            resolved_artifacts["packet1_facts"] = merged_packet1_facts
        existing_packet2_facts = dict(resolved_artifacts.get("packet2_facts") or {})
        merged_packet2_facts = {
            **existing_packet2_facts,
            **dict(packet2_artifacts.get("packet2_facts") or {}),
        }
        if merged_packet2_facts:
            resolved_artifacts["packet2_facts"] = merged_packet2_facts
        existing_artifact_provenance_facts = normalize_artifact_provenance_facts(
            resolved_artifacts.get("artifact_provenance_facts")
        )
        merged_artifact_provenance_facts = {
            **existing_artifact_provenance_facts,
            **normalize_artifact_provenance_facts(artifact_provenance_artifacts.get("artifact_provenance_facts")),
        }
        if merged_artifact_provenance_facts:
            resolved_artifacts["artifact_provenance_facts"] = merged_artifact_provenance_facts
        if cards_runtime_artifacts:
            resolved_artifacts.update(cards_runtime_artifacts)
        runtime_verification_path = str(packet1_artifacts.get("runtime_verification_path") or "").strip()
        if runtime_verification_path:
            resolved_artifacts["runtime_verification_path"] = runtime_verification_path
        try:
            run_identity = resolved_artifacts.get("run_identity")
            started_at = None
            if run_identity is not None:
                started_at = validate_run_identity_projection(
                    run_identity,
                    error_prefix="run_summary_run_identity",
                )["start_time"]
            run_summary = await generate_run_summary_for_finalize(
                workspace=self.workspace,
                run_id=run_id,
                status=session_status,
                failure_reason=failure_reason,
                started_at=started_at,
                ended_at=finalized_at,
                artifacts=resolved_artifacts,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            if _is_run_summary_run_identity_error(exc):
                _strip_transient_run_identity_artifacts(resolved_artifacts)
            resolved_artifacts["run_summary_generation_error"] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            await self._record_packet1_emission_failure(
                run_id=run_id,
                stage="generation",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            log_event(
                "run_summary_generation_failed",
                {"run_id": run_id, "error_type": type(exc).__name__, "error": str(exc)},
                workspace=self.workspace,
            )
            run_summary = build_degraded_run_summary_payload(
                run_id=run_id,
                status=session_status,
                failure_reason=failure_reason,
                artifacts=resolved_artifacts,
            )
        try:
            run_summary_path = await write_run_summary_artifact(
                root=self.workspace,
                session_id=run_id,
                payload=run_summary,
            )
            resolved_artifacts["run_summary_path"] = str(run_summary_path)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            await self._record_packet1_emission_failure(
                run_id=run_id,
                stage="write",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            log_event(
                "run_summary_artifact_write_failed",
                {"run_id": run_id, "error_type": type(exc).__name__, "error": str(exc)},
                workspace=self.workspace,
            )
        resolved_artifacts["run_summary"] = dict(run_summary)
        return run_summary, resolved_artifacts
