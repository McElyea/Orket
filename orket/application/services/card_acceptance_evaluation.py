"""Interpret admitted card checks, then use the shared core acceptance policy."""
from __future__ import annotations

import base64
import hashlib
import json

from orket.adapters.storage.card_acceptance_artifacts import (
    MAX_SNAPSHOT_BYTES,
    CapturedCardArtifact,
    artifact_manifest_digest,
)
from orket.application.services.card_artifact_acceptance_evaluation import (
    artifact_acceptance_evidence,
    build_artifact_acceptance_plan,
)
from orket.application.services.runtime_verifier_capture import COMMAND_OUTPUT_LIMIT, stdout_capture_error
from orket.core.contracts.card_acceptance_inputs import (
    ArtifactAcceptance,
    CardAcceptanceDefinition,
    CardAcceptancePackage,
    PythonCliAcceptance,
    PythonCliAcceptanceCase,
    RetainedCardCommand,
    normalized_json_text,
)
from orket.core.contracts.card_completion import (
    AcceptanceRequirement,
    CardAcceptanceEvidence,
    CardAcceptancePlan,
    CardCompletionDecision,
    CompletionEvidenceSnapshot,
    CompletionScope,
)
from orket.core.policies.card_completion import evaluate_card_completion

VERIFIER_REF = "python_cli_exact_json.v1"


def _verifier_digest(definition: PythonCliAcceptance, case: PythonCliAcceptanceCase) -> str:
    specification = {
        "verifier_ref": VERIFIER_REF, "entrypoint": definition.entrypoint, "case": case.model_dump(mode="json"),
        "interpreter_flags": ["-I", "-B"], "output_limit_characters": COMMAND_OUTPUT_LIMIT,
        "acceptance": "declared Python sources compile, exit zero, lossless UTF-8 standard JSON, exact normalized JSON equality, unchanged snapshot",
    }
    return hashlib.sha256(json.dumps(specification, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_card_acceptance_plan(definition: CardAcceptanceDefinition) -> CardAcceptancePlan:
    if isinstance(definition, ArtifactAcceptance):
        return build_artifact_acceptance_plan(definition)
    return CardAcceptancePlan(
        acceptance_ref=definition.acceptance_ref, policy_ref=definition.policy_ref, policy_digest=definition.digest,
        workload_id=definition.workload_id, requirements=tuple(AcceptanceRequirement(
            criterion_id=case.criterion_id, description=case.description, verifier_ref=VERIFIER_REF,
            verifier_digest=_verifier_digest(definition, case), evidence_class="behavioral_verification",
        ) for case in definition.cases),
    )


def evaluate_card_acceptance_package(
    package: CardAcceptancePackage, *, definition: CardAcceptanceDefinition, scope: CompletionScope
) -> CardCompletionDecision:
    plan = build_card_acceptance_plan(definition)
    diagnostics = list(package.diagnostics)
    if package.plan != plan or package.definition != definition:
        diagnostics.append("retained_acceptance_plan_mismatch")
    if hashlib.sha256(package.inputs_json.encode("utf-8")).hexdigest() != package.scope.input_digest:
        diagnostics.append("retained_input_digest_mismatch")
    artifacts: list[CapturedCardArtifact] = []
    for artifact in package.artifacts:
        content = base64.b64decode(artifact.content_base64, validate=True)
        if len(content) != artifact.size_bytes or hashlib.sha256(content).hexdigest() != artifact.sha256:
            diagnostics.append("retained_artifact_digest_mismatch")
        artifacts.append(CapturedCardArtifact(path=artifact.path, content=content))
    if sum(len(row.content) for row in artifacts) > MAX_SNAPSHOT_BYTES:
        diagnostics.append("retained_artifact_resource_limit")
    if sorted(row.path for row in artifacts) != sorted(definition.artifact_paths):
        diagnostics.append("retained_artifact_inventory_mismatch")
    if artifact_manifest_digest(tuple(artifacts)) != package.scope.artifact_manifest_digest:
        diagnostics.append("retained_artifact_manifest_mismatch")
    if isinstance(definition, ArtifactAcceptance):
        records = artifact_acceptance_evidence(
            definition=definition, plan=plan, scope=package.scope, artifacts=tuple(artifacts),
        )
    else:
        records = tuple(_evidence_for_command(command, package) for command in package.commands)
    snapshot = CompletionEvidenceSnapshot(
        records=records, inventory_complete=len(records) == len(definition.cases), diagnostics=tuple(diagnostics),
    )
    return evaluate_card_completion(plan=plan, scope=scope, snapshot=snapshot)


def _evidence_for_command(command: RetainedCardCommand, package: CardAcceptancePackage) -> CardAcceptanceEvidence:
    if not isinstance(package.definition, PythonCliAcceptance):
        raise ValueError("E_CARD_ACCEPTANCE_COMMAND_FAMILY")
    body = json.loads(command.result_json)
    case = next((row for row in package.definition.cases if row.criterion_id == command.criterion_id), None)
    if not isinstance(body, dict) or not isinstance(body.get("errors"), list):
        raise ValueError("E_CARD_ACCEPTANCE_COMMAND_RECORD")
    commands = body.get("command_results")
    if not isinstance(commands, list) or len(commands) != 1 or not isinstance(commands[0], dict):
        raise ValueError("E_CARD_ACCEPTANCE_COMMAND_INVENTORY")
    observed = commands[0]
    inputs = json.loads(package.inputs_json)
    if case is not None:
        expected_argv = [inputs["runtime"]["executable"], "-I", "-B", package.definition.entrypoint, *case.arguments]
        if observed.get("argv") != expected_argv or observed.get("working_directory") != ".":
            raise ValueError("E_CARD_ACCEPTANCE_COMMAND_BINDING")
    passed = False
    if (case is not None and not body["errors"] and type(observed.get("returncode")) is int
            and observed["returncode"] == 0 and stdout_capture_error(observed) is None):
        try:
            raw = observed["stdout"].encode("utf-8")
            capture_matches = (hashlib.sha256(raw).hexdigest() == observed.get("stdout_sha256")
                               and len(raw) == observed.get("stdout_bytes"))
            passed = capture_matches and normalized_json_text(observed["stdout"]) == case.expected_json
        except (ValueError, TypeError, KeyError):
            passed = False
    digest = hashlib.sha256(command.result_json.encode("utf-8")).hexdigest()
    return CardAcceptanceEvidence(
        evidence_ref=f"card-command:{package.scope.attempt_id}:{command.criterion_id}:{digest}", evidence_digest=digest,
        plan_digest=package.plan.digest, scope=package.scope, criterion_id=command.criterion_id,
        verifier_ref=VERIFIER_REF, verifier_digest=_verifier_digest(package.definition, case) if case else "0" * 64,
        evidence_class="behavioral_verification", observation="passed" if passed else "failed", source="runtime_verifier",
    )
