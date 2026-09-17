"""Application-owned execution and retained evidence for declared card acceptance."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import aiosqlite

from orket.adapters.storage.card_acceptance_artifacts import (
    CapturedCardArtifact,
    CardAcceptanceArtifacts,
    artifact_manifest_digest,
)
from orket.adapters.storage.card_acceptance_evidence_store import CardAcceptanceEvidenceStore
from orket.application.services.card_acceptance_evaluation import (
    build_card_acceptance_plan,
    evaluate_card_acceptance_package,
)
from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.core.contracts.card_acceptance_inputs import (
    ArtifactAcceptance,
    CardAcceptanceDefinition,
    CardAcceptancePackage,
    PythonCliAcceptance,
    PythonCliAcceptanceCase,
    RetainedCardArtifact,
    RetainedCardCommand,
    normalized_json_text,
)
from orket.core.contracts.card_completion import CardCompletionDecision, CompletionEvidenceSnapshot, CompletionScope
from orket.core.policies.card_completion import evaluate_card_completion
from orket.extensions.governed_agent_process import sanitized_agent_environment


@dataclass(frozen=True)
class CardAcceptanceEvaluation:
    evidence_digest: str | None
    decision: CardCompletionDecision


@dataclass(frozen=True)
class CardAcceptanceCapture:
    inputs_json: str
    environment: dict[str, str]
    scope: CompletionScope
    artifacts: tuple[CapturedCardArtifact, ...]
    diagnostics: tuple[str, ...]


class CardAcceptanceService:
    """Verifies explicit acceptance only; final card transitions are a separate gate."""

    def __init__(self, evidence_store: CardAcceptanceEvidenceStore):
        self.evidence_store = evidence_store
        self.artifacts = CardAcceptanceArtifacts()

    async def verify(
        self, *, workspace_root: Path, definition: CardAcceptanceDefinition | None,
        card_id: str, run_id: str, attempt_id: str, workload_inputs_json: str,
    ) -> CardAcceptanceEvaluation:
        if definition is None:
            return CardAcceptanceEvaluation(None, evaluate_card_completion(
                plan=None, scope=None, snapshot=CompletionEvidenceSnapshot(),
            ))
        cancel_requested = asyncio.Event()
        task = asyncio.create_task(self._verify(
            workspace_root, definition, card_id, run_id, attempt_id, workload_inputs_json, cancel_requested,
        ))
        joined = asyncio.gather(task, return_exceptions=True)
        while True:
            try:
                result, = await asyncio.shield(joined)
                break
            except asyncio.CancelledError:
                # Cancellation stops case admission; the current verifier owns its child until it returns.
                cancel_requested.set()
        if cancel_requested.is_set():
            if isinstance(result, BaseException):
                logging.getLogger(__name__).warning("Card acceptance failed during cancellation cleanup: %r", result)
            raise asyncio.CancelledError
        if isinstance(result, BaseException):
            raise result
        return result

    async def inspect(
        self, evidence_digest: str, *, definition: CardAcceptanceDefinition, scope: CompletionScope,
    ) -> CardCompletionDecision:
        try:
            payload = await self.evidence_store.read(evidence_digest)
            if payload is None:
                raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_MISSING")
            package = CardAcceptancePackage.model_validate_json(payload)
            return evaluate_card_acceptance_package(package, definition=definition, scope=scope)
        except (ValueError, OSError, aiosqlite.Error, KeyError, TypeError) as exc:
            return evaluate_card_completion(
                plan=build_card_acceptance_plan(definition), scope=scope,
                snapshot=CompletionEvidenceSnapshot(diagnostics=(f"retained_evidence_unverifiable:{type(exc).__name__}:{exc}",)),
            )

    async def capture_scope(
        self, *, workspace_root: Path, definition: CardAcceptanceDefinition, card_id: str, run_id: str, attempt_id: str,
        workload_inputs_json: str,
    ) -> CardAcceptanceCapture:
        environment = sanitized_agent_environment() if isinstance(definition, PythonCliAcceptance) else {}
        runtime = ({"executable": sys.executable, "version": sys.version, "environment": environment}
                   if isinstance(definition, PythonCliAcceptance) else {"verifier": "card_artifact_verifier.v1"})
        inputs_json = normalized_json_text(json.dumps({
            "schema_version": "card_acceptance_inputs.v1", "workload_inputs": json.loads(normalized_json_text(workload_inputs_json)),
            "runtime": runtime,
        }))
        diagnostics: list[str] = []
        captured: tuple[CapturedCardArtifact, ...] = ()
        try:
            captured = await self.artifacts.capture(workspace_root, definition.artifact_paths)
        except (ValueError, OSError, RuntimeError) as exc:
            diagnostics.append(f"artifact_capture_failed:{type(exc).__name__}:{exc}")
        scope = CompletionScope(
            card_id=card_id, run_id=run_id, attempt_id=attempt_id, workload_id=definition.workload_id,
            input_digest=hashlib.sha256(inputs_json.encode("utf-8")).hexdigest(),
            artifact_manifest_digest=artifact_manifest_digest(captured),
        )
        return CardAcceptanceCapture(inputs_json, environment, scope, captured, tuple(diagnostics))

    async def _verify(
        self, workspace_root: Path, definition: CardAcceptanceDefinition, card_id: str, run_id: str, attempt_id: str,
        workload_inputs_json: str, cancel_requested: asyncio.Event,
    ) -> CardAcceptanceEvaluation:
        capture = await self.capture_scope(
            workspace_root=workspace_root, definition=definition, card_id=card_id, run_id=run_id,
            attempt_id=attempt_id, workload_inputs_json=workload_inputs_json,
        )
        inputs_json, environment, scope = capture.inputs_json, capture.environment, capture.scope
        captured, diagnostics = capture.artifacts, list(capture.diagnostics)
        commands: list[RetainedCardCommand] = []
        if not diagnostics and isinstance(definition, PythonCliAcceptance):
            for case in definition.cases:
                if cancel_requested.is_set():
                    break
                command, case_diagnostics = await self._execute_case(definition, case, captured, environment)
                commands.append(command)
                diagnostics.extend(case_diagnostics)
        if cancel_requested.is_set():
            diagnostics.append("verification_cancelled")
        package = CardAcceptancePackage(
            schema_version="card_acceptance_package.v2" if isinstance(definition, ArtifactAcceptance) else "card_acceptance_package.v1",
            definition=definition, plan=build_card_acceptance_plan(definition), scope=scope, inputs_json=inputs_json,
            artifacts=tuple(RetainedCardArtifact(
                **artifact.manifest_entry, content_base64=base64.b64encode(artifact.content).decode("ascii"),
            ) for artifact in captured), commands=tuple(commands), diagnostics=tuple(diagnostics),
        )
        digest = await self.evidence_store.put(package.model_dump_json())
        decision = await self.inspect(digest, definition=definition, scope=scope)
        return CardAcceptanceEvaluation(digest, decision)

    async def _execute_case(
        self, definition: PythonCliAcceptance, case: PythonCliAcceptanceCase,
        captured: tuple[CapturedCardArtifact, ...], environment: dict[str, str],
    ) -> tuple[RetainedCardCommand, list[str]]:
        temporary = await asyncio.to_thread(tempfile.TemporaryDirectory, prefix="orket-card-acceptance-")
        root = await asyncio.to_thread(Path(temporary.name).resolve)
        parent = root.parent
        diagnostics: list[str] = []
        try:
            await self.artifacts.materialize(root, captured)
            verifier = RuntimeVerifier(root, organization=SimpleNamespace(process_rules={
                "runtime_verifier_timeout_sec": definition.timeout_seconds,
            }), issue_params={"runtime_verifier": {
                "commands": [[sys.executable, "-I", "-B", definition.entrypoint, *case.arguments]],
                "expect_json_stdout": True,
            }}, command_environment=environment)
            result = await verifier.verify()
            try:
                after = await self.artifacts.capture(root, definition.artifact_paths)
                if artifact_manifest_digest(after) != artifact_manifest_digest(captured):
                    diagnostics.append(f"{case.criterion_id}:verification_snapshot_changed")
            except (ValueError, OSError, RuntimeError) as exc:
                diagnostics.append(f"{case.criterion_id}:verification_snapshot_unreadable:{type(exc).__name__}:{exc}")
            body: dict[str, Any] = {
                "errors": result.errors, "checked_files": result.checked_files, "command_results": result.command_results,
                "overall_evidence_class": result.overall_evidence_class, "failure_breakdown": result.failure_breakdown,
            }
            return RetainedCardCommand(criterion_id=case.criterion_id, result_json=json.dumps(body, sort_keys=True)), diagnostics
        finally:
            resolved = await asyncio.to_thread(root.resolve)
            if resolved != root or not resolved.is_relative_to(parent) or resolved == parent:
                raise RuntimeError("E_CARD_ACCEPTANCE_CLEANUP_TARGET_CHANGED")
            await asyncio.to_thread(temporary.cleanup)
