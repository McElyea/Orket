from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus, CardType


class CardAuthoringNotFoundError(Exception):
    """Raised when the requested card id does not exist."""


class CardAuthoringConflictError(Exception):
    """Raised when the caller acts on stale revision state."""


class CardDraftWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    card_kind: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    inputs: Any
    expected_outputs: Any
    expected_output_type: str = Field(min_length=1)
    display_category: str = Field(min_length=1)
    notes: str
    constraints: Any
    approval_expectation: str = Field(min_length=1)
    artifact_expectation: str = Field(min_length=1)

    @field_validator("card_kind")
    @classmethod
    def normalize_card_kind(cls, value: str) -> str:
        return str(value or "").strip().lower().replace(" ", "_")

    @field_validator("inputs", "expected_outputs", "constraints", mode="before")
    @classmethod
    def require_payload_value(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("field is required")
        return value


class CardValidationResult(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    summary: str
    reason_codes: list[str]


class CardWriteResult(BaseModel):
    card_id: str
    revision_id: str
    saved_at: str
    validation: CardValidationResult
    degraded: bool
    summary: str
    reason_codes: list[str]


class CardAuthoringService:
    def __init__(
        self,
        *,
        cards_repo: Any,
        now_iso_factory: Callable[[], str],
        card_id_factory: Callable[[], str],
        revision_id_factory: Callable[[], str],
        runtime_projection_service: Any | None = None,
    ) -> None:
        self._cards_repo = cards_repo
        self._now_iso_factory = now_iso_factory
        self._card_id_factory = card_id_factory
        self._revision_id_factory = revision_id_factory
        self._runtime_projection_service = runtime_projection_service

    async def create_card(self, draft: CardDraftWriteModel) -> CardWriteResult:
        validation = self.validate_draft(draft)
        card_id = self._card_id_factory()
        revision_id = self._revision_id_factory()
        saved_at = self._now_iso_factory()
        record = IssueRecord.model_validate(
            {
                "id": card_id,
                "summary": draft.name,
                "seat": self._resolve_authoring_seat(draft.card_kind),
                "status": CardStatus.READY,
                "type": self._resolve_card_type(draft.card_kind),
                "note": draft.notes,
                "params": self._build_params(existing=None, draft=draft, revision_id=revision_id, saved_at=saved_at),
                "verification": {
                    "authoring_validation": validation.model_dump(),
                },
                "metrics": {},
                "created_at": saved_at,
            }
        )
        await self._cards_repo.save(record)
        await self._sync_runtime_projection(record)
        await self._append_transaction_if_supported(card_id=card_id, action=f"Created authored card revision '{revision_id}'")
        return CardWriteResult(
            card_id=card_id,
            revision_id=revision_id,
            saved_at=saved_at,
            validation=validation,
            degraded=False,
            summary="Card created and persisted through the host card authoring surface.",
            reason_codes=["card_authoring.created"],
        )

    async def update_card(
        self,
        *,
        card_id: str,
        draft: CardDraftWriteModel,
        expected_revision_id: str | None = None,
    ) -> CardWriteResult:
        existing = await self._cards_repo.get_by_id(card_id)
        if existing is None:
            raise CardAuthoringNotFoundError(card_id)

        current_revision_id = self._read_revision_id(existing.params)
        if expected_revision_id and current_revision_id and expected_revision_id != current_revision_id:
            raise CardAuthoringConflictError(
                f"revision_conflict: expected '{expected_revision_id}' but found '{current_revision_id}'"
            )

        validation = self.validate_draft(draft)
        revision_id = self._revision_id_factory()
        saved_at = self._now_iso_factory()
        record = IssueRecord.model_validate(
            {
                **existing.model_dump(),
                "id": card_id,
                "summary": draft.name,
                "seat": self._resolve_authoring_seat(draft.card_kind),
                "type": self._resolve_card_type(draft.card_kind),
                "note": draft.notes,
                "params": self._build_params(
                    existing=existing.params,
                    draft=draft,
                    revision_id=revision_id,
                    saved_at=saved_at,
                ),
                "verification": {
                    **dict(existing.verification or {}),
                    "authoring_validation": validation.model_dump(),
                },
            }
        )
        await self._cards_repo.save(record)
        await self._sync_runtime_projection(record)
        await self._append_transaction_if_supported(card_id=card_id, action=f"Saved authored card revision '{revision_id}'")
        return CardWriteResult(
            card_id=card_id,
            revision_id=revision_id,
            saved_at=saved_at,
            validation=validation,
            degraded=False,
            summary="Card save confirmed through the host card authoring surface.",
            reason_codes=["card_authoring.saved"],
        )

    def validate_draft(self, draft: CardDraftWriteModel | dict[str, Any]) -> CardValidationResult:
        try:
            resolved = draft if isinstance(draft, CardDraftWriteModel) else CardDraftWriteModel.model_validate(draft)
        except ValidationError as exc:
            errors = [f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()]
            return CardValidationResult(
                is_valid=False,
                errors=errors,
                warnings=[],
                summary="Card authoring payload is invalid.",
                reason_codes=["card_authoring.validation_failed"],
            )

        warnings: list[str] = []
        if resolved.card_kind not in {"epic", "rock", "utility", "app", "issue"}:
            warnings.append(
                "Extension-local card kind was normalized onto host issue semantics; original label remains in authoring metadata."
            )

        return CardValidationResult(
            is_valid=True,
            errors=[],
            warnings=warnings,
            summary="Card authoring payload is valid.",
            reason_codes=["card_authoring.valid"],
        )

    async def _append_transaction_if_supported(self, *, card_id: str, action: str) -> None:
        add_transaction = getattr(self._cards_repo, "add_transaction", None)
        if callable(add_transaction):
            await cast(Callable[[str, str, str], Awaitable[None]], add_transaction)(card_id, "api", action)

    def _build_params(
        self,
        *,
        existing: dict[str, Any] | None,
        draft: CardDraftWriteModel,
        revision_id: str,
        saved_at: str,
    ) -> dict[str, Any]:
        params = dict(existing or {})
        params["authoring_revision_id"] = revision_id
        params["authoring_saved_at"] = saved_at
        params["authoring_payload"] = draft.model_dump()
        params["prompt"] = draft.prompt
        params["purpose"] = draft.purpose
        params["display_category"] = draft.display_category
        params["expected_output_type"] = draft.expected_output_type
        params["approval_expectation"] = draft.approval_expectation
        params["artifact_expectation"] = draft.artifact_expectation
        params["constraints"] = draft.constraints
        params["inputs"] = draft.inputs
        params["expected_outputs"] = draft.expected_outputs
        params["original_card_kind"] = draft.card_kind
        return params

    def _read_revision_id(self, params: dict[str, Any] | None) -> str | None:
        value = dict(params or {}).get("authoring_revision_id")
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _resolve_card_type(self, card_kind: str) -> CardType:
        normalized = str(card_kind or "").strip().lower().replace(" ", "_")
        mapping = {
            "issue": CardType.ISSUE,
            "task": CardType.ISSUE,
            "requirement": CardType.ISSUE,
            "code": CardType.ISSUE,
            "critique": CardType.ISSUE,
            "approval": CardType.ISSUE,
            "epic": CardType.EPIC,
            "rock": CardType.ROCK,
            "utility": CardType.UTILITY,
            "app": CardType.APP,
        }
        return mapping.get(normalized, CardType.ISSUE)

    def _resolve_authoring_seat(self, card_kind: str) -> str:
        normalized = str(card_kind or "").strip().lower().replace(" ", "_")
        mapping = {
            "requirement": "requirements_analyst",
            "code": "coder",
            "critique": "quality_assurance",
            "approval": "code_reviewer",
        }
        return mapping.get(normalized, "coder")

    async def _sync_runtime_projection(self, record: IssueRecord) -> None:
        if self._runtime_projection_service is None:
            return
        await self._runtime_projection_service.upsert_card_record(record)
