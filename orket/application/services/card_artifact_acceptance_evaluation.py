"""Compare declared artifact criteria against captured bytes without running them."""
from __future__ import annotations

import hashlib
import json

from orket.adapters.storage.card_acceptance_artifacts import CapturedCardArtifact
from orket.core.contracts.card_acceptance_inputs import (
    ArtifactAcceptance,
    ArtifactAcceptanceCase,
    TextArtifactAcceptanceCase,
    normalized_json_text,
)
from orket.core.contracts.card_completion import (
    AcceptanceRequirement,
    CardAcceptanceEvidence,
    CardAcceptancePlan,
    CompletionScope,
)


def _verifier_ref(case: ArtifactAcceptanceCase) -> str:
    return f"artifact_{case.kind}.v1"


def _verifier_digest(case: ArtifactAcceptanceCase) -> str:
    specification = {
        "verifier_ref": _verifier_ref(case), "case": case.model_dump(mode="json"),
        "encoding": "strict UTF-8", "text_normalization": "none",
        "json": "standard JSON; reject duplicate keys and non-finite numbers; traverse object keys only; compare normalized JSON",
    }
    return hashlib.sha256(json.dumps(specification, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_artifact_acceptance_plan(definition: ArtifactAcceptance) -> CardAcceptancePlan:
    return CardAcceptancePlan(
        acceptance_ref=definition.acceptance_ref, policy_ref=definition.policy_ref, policy_digest=definition.digest,
        workload_id=definition.workload_id, requirements=tuple(AcceptanceRequirement(
            criterion_id=case.criterion_id, description=case.description, verifier_ref=_verifier_ref(case),
            verifier_digest=_verifier_digest(case), evidence_class="artifact_verification",
        ) for case in definition.cases),
    )


def _matches(case: ArtifactAcceptanceCase, content: bytes) -> bool:
    try:
        text = content.decode("utf-8")
        if isinstance(case, TextArtifactAcceptanceCase):
            return text == case.expected_text
        value = json.loads(normalized_json_text(text))
        for key in case.key_path:
            if not isinstance(value, dict):
                return False
            value = value[key]
        return normalized_json_text(json.dumps(value)) == case.expected_json
    except (ValueError, KeyError, TypeError):
        return False


def artifact_acceptance_evidence(
    *, definition: ArtifactAcceptance, plan: CardAcceptancePlan, scope: CompletionScope,
    artifacts: tuple[CapturedCardArtifact, ...],
) -> tuple[CardAcceptanceEvidence, ...]:
    by_path = {artifact.path: artifact.content for artifact in artifacts}
    records = []
    for case in definition.cases:
        if case.path not in by_path:
            continue
        content = by_path[case.path]
        digest = hashlib.sha256(content).hexdigest()
        records.append(CardAcceptanceEvidence(
            evidence_ref=f"card-artifact:{scope.attempt_id}:{case.criterion_id}:{digest}", evidence_digest=digest,
            plan_digest=plan.digest, scope=scope, criterion_id=case.criterion_id,
            verifier_ref=_verifier_ref(case), verifier_digest=_verifier_digest(case),
            evidence_class="artifact_verification", observation="passed" if _matches(case, content) else "failed",
            source="runtime_verifier",
        ))
    return tuple(records)
