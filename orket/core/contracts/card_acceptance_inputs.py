"""Explicit inputs for bounded CLI behavior and artifact acceptance verifiers."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from orket.core.contracts.card_completion import (
    CardAcceptancePlan,
    CompletionRecord,
    CompletionScope,
    Reference,
    Sha256,
)

CliArgument = Annotated[str, Field(strict=True, max_length=4096, pattern=r"^[^\x00]*$")]


def validate_artifact_paths(paths: tuple[str, ...]) -> None:
    if len(set(paths)) != len(paths):
        raise ValueError("Duplicate acceptance artifact path")
    for path in paths:
        parts = PurePosixPath(path).parts
        if (len(parts) < 2 or parts[0] != "agent_output" or any(part in {"", ".", ".."} for part in path.split("/"))
                or "\\" in path or ":" in path or "\x00" in path):
            raise ValueError("Acceptance artifacts require normalized relative agent_output paths")


def normalized_json_text(text: str) -> str:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object member")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-JSON numeric constant: {value}")

    value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class PythonCliAcceptanceCase(CompletionRecord):
    criterion_id: Reference
    description: Reference
    arguments: tuple[CliArgument, ...] = Field(default=(), max_length=32)
    expected_json: Annotated[str, Field(strict=True, max_length=2000)]

    @field_validator("expected_json")
    @classmethod
    def validate_json(cls, value: str) -> str:
        return normalized_expected_json(value)


def normalized_expected_json(value: str) -> str:
    normalized = normalized_json_text(value)
    if len(normalized) > 2000:
        raise ValueError("Normalized expected JSON exceeds the accepted output limit")
    return normalized


class PythonCliAcceptance(CompletionRecord):
    schema_version: Literal["card_python_cli_acceptance.v1"] = "card_python_cli_acceptance.v1"
    acceptance_ref: Reference
    policy_ref: Reference
    workload_id: Reference
    entrypoint: Reference
    artifact_paths: tuple[Reference, ...] = Field(min_length=1, max_length=64)
    cases: tuple[PythonCliAcceptanceCase, ...] = Field(min_length=1, max_length=32)
    timeout_seconds: Annotated[int, Field(strict=True, ge=1, le=60)] = 30

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        validate_artifact_paths(self.artifact_paths)
        if self.entrypoint not in self.artifact_paths or not self.entrypoint.endswith(".py"):
            raise ValueError("Acceptance entrypoint must be a declared Python artifact")
        if len({case.criterion_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate acceptance criterion")
        return self

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


class RetainedCardArtifact(CompletionRecord):
    path: Reference
    sha256: Sha256
    size_bytes: Annotated[int, Field(strict=True, ge=0, le=1_048_576)]
    content_base64: Annotated[str, Field(strict=True, max_length=1_398_104)]


class TextArtifactAcceptanceCase(CompletionRecord):
    kind: Literal["text_equals"]
    criterion_id: Reference
    description: Reference
    path: Reference
    expected_text: Annotated[str, Field(strict=True, max_length=4096)]

    @field_validator("expected_text")
    @classmethod
    def validate_utf8(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 4096:
            raise ValueError("Expected artifact text exceeds 4096 UTF-8 bytes")
        return value


class JsonArtifactAcceptanceCase(CompletionRecord):
    kind: Literal["json_value_equals"]
    criterion_id: Reference
    description: Reference
    path: Reference
    key_path: tuple[Reference, ...] = Field(default=(), max_length=16)
    expected_json: Annotated[str, Field(strict=True, max_length=2000)]

    @field_validator("expected_json")
    @classmethod
    def validate_json(cls, value: str) -> str:
        return normalized_expected_json(value)


ArtifactAcceptanceCase = Annotated[TextArtifactAcceptanceCase | JsonArtifactAcceptanceCase, Field(discriminator="kind")]


class ArtifactAcceptance(CompletionRecord):
    schema_version: Literal["card_artifact_acceptance.v1"]
    acceptance_ref: Reference
    policy_ref: Reference
    workload_id: Reference
    artifact_paths: tuple[Reference, ...] = Field(min_length=1, max_length=64)
    cases: tuple[ArtifactAcceptanceCase, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        validate_artifact_paths(self.artifact_paths)
        if len({case.criterion_id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate acceptance criterion")
        if any(case.path not in self.artifact_paths for case in self.cases):
            raise ValueError("Acceptance case refers to an undeclared artifact")
        return self

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode("utf-8")).hexdigest()


CardAcceptanceDefinition = PythonCliAcceptance | ArtifactAcceptance


class RetainedCardCommand(CompletionRecord):
    criterion_id: Reference
    result_json: Annotated[str, Field(strict=True, max_length=524_288)]


class CardAcceptancePackage(CompletionRecord):
    schema_version: Literal["card_acceptance_package.v1", "card_acceptance_package.v2"] = "card_acceptance_package.v1"
    definition: CardAcceptanceDefinition
    plan: CardAcceptancePlan
    scope: CompletionScope
    inputs_json: Annotated[str, Field(strict=True, max_length=1_048_576)]
    artifacts: tuple[RetainedCardArtifact, ...] = Field(max_length=64)
    commands: tuple[RetainedCardCommand, ...] = Field(max_length=32)
    diagnostics: tuple[Reference, ...] = ()

    @model_validator(mode="after")
    def require_family_version(self) -> Self:
        artifact_family = isinstance(self.definition, ArtifactAcceptance)
        if artifact_family != (self.schema_version == "card_acceptance_package.v2"):
            raise ValueError("Acceptance package version does not match its verifier family")
        if artifact_family and self.commands:
            raise ValueError("Artifact acceptance cannot contain command execution receipts")
        return self
