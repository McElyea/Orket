from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class FlowAuthoringNotFoundError(Exception):
    """Raised when the requested flow id does not exist."""


class FlowAuthoringConflictError(Exception):
    """Raised when the caller acts on stale revision state."""


class FlowRuntimeNotAdmittedError(Exception):
    """Raised when the saved flow cannot truthfully map to the shipped run slice."""


class FlowNodeWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    label: str = Field(min_length=1)
    assigned_card_id: str | None = None
    notes: str = ""

    @field_validator("kind")
    @classmethod
    def normalize_kind(cls, value: str) -> str:
        return str(value or "").strip().lower().replace(" ", "_")


class FlowEdgeWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(min_length=1)
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    condition_label: str = ""


class FlowDefinitionWriteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    nodes: list[FlowNodeWriteModel]
    edges: list[FlowEdgeWriteModel]


class FlowValidationResult(BaseModel):
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    summary: str
    reason_codes: list[str]


class FlowWriteResult(BaseModel):
    flow_id: str
    revision_id: str
    saved_at: str
    validation: FlowValidationResult
    degraded: bool
    summary: str
    reason_codes: list[str]


class FlowRunAccepted(BaseModel):
    flow_id: str
    revision_id: str
    session_id: str
    accepted_at: str
    summary: str


class FlowAuthoringService:
    def __init__(
        self,
        *,
        flow_repo: Any,
        now_iso_factory: Callable[[], str],
        flow_id_factory: Callable[[], str],
        revision_id_factory: Callable[[], str],
    ) -> None:
        self._flow_repo = flow_repo
        self._now_iso_factory = now_iso_factory
        self._flow_id_factory = flow_id_factory
        self._revision_id_factory = revision_id_factory

    async def list_flows(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        items = await self._flow_repo.list_flows(limit=limit, offset=offset)
        return {
            "items": [
                {
                    "flow_id": str(item.get("flow_id") or ""),
                    "revision_id": str(item.get("revision_id") or ""),
                    "name": str(item.get("name") or ""),
                    "description": str(item.get("description") or ""),
                    "node_count": len(list((item.get("payload") or {}).get("nodes") or [])),
                    "edge_count": len(list((item.get("payload") or {}).get("edges") or [])),
                    "updated_at": str(item.get("updated_at") or ""),
                }
                for item in items
            ],
            "count": len(items),
            "limit": limit,
            "offset": offset,
        }

    async def get_flow(self, flow_id: str) -> dict[str, Any]:
        existing = await self._flow_repo.get_flow(flow_id)
        if existing is None:
            raise FlowAuthoringNotFoundError(flow_id)
        payload = dict(existing.get("payload") or {})
        return {
            "flow_id": str(existing.get("flow_id") or flow_id),
            "revision_id": str(existing.get("revision_id") or ""),
            "name": str(existing.get("name") or ""),
            "description": str(existing.get("description") or ""),
            "nodes": list(payload.get("nodes") or []),
            "edges": list(payload.get("edges") or []),
            "created_at": str(existing.get("created_at") or ""),
            "updated_at": str(existing.get("updated_at") or ""),
        }

    async def create_flow(self, definition: FlowDefinitionWriteModel) -> FlowWriteResult:
        validation = self.validate_definition(definition)
        flow_id = self._flow_id_factory()
        revision_id = self._revision_id_factory()
        saved_at = self._now_iso_factory()
        await self._flow_repo.save_flow(
            flow_id=flow_id,
            revision_id=revision_id,
            name=definition.name,
            description=definition.description,
            payload=definition.model_dump(),
            created_at=saved_at,
            updated_at=saved_at,
        )
        return FlowWriteResult(
            flow_id=flow_id,
            revision_id=revision_id,
            saved_at=saved_at,
            validation=validation,
            degraded=False,
            summary="Flow definition created and persisted through the host flow authoring surface.",
            reason_codes=["flow_authoring.created"],
        )

    async def update_flow(
        self,
        *,
        flow_id: str,
        definition: FlowDefinitionWriteModel,
        expected_revision_id: str | None = None,
    ) -> FlowWriteResult:
        existing = await self._flow_repo.get_flow(flow_id)
        if existing is None:
            raise FlowAuthoringNotFoundError(flow_id)

        current_revision_id = str(existing.get("revision_id") or "").strip() or None
        if expected_revision_id and current_revision_id and expected_revision_id != current_revision_id:
            raise FlowAuthoringConflictError(
                f"revision_conflict: expected '{expected_revision_id}' but found '{current_revision_id}'"
            )

        validation = self.validate_definition(definition)
        revision_id = self._revision_id_factory()
        now_iso = self._now_iso_factory()
        await self._flow_repo.save_flow(
            flow_id=flow_id,
            revision_id=revision_id,
            name=definition.name,
            description=definition.description,
            payload=definition.model_dump(),
            created_at=str(existing.get("created_at") or now_iso),
            updated_at=now_iso,
        )
        return FlowWriteResult(
            flow_id=flow_id,
            revision_id=revision_id,
            saved_at=now_iso,
            validation=validation,
            degraded=False,
            summary="Flow save confirmed through the host flow authoring surface.",
            reason_codes=["flow_authoring.saved"],
        )

    def validate_definition(self, definition: FlowDefinitionWriteModel | dict[str, Any]) -> FlowValidationResult:
        try:
            resolved = definition if isinstance(definition, FlowDefinitionWriteModel) else FlowDefinitionWriteModel.model_validate(definition)
        except ValidationError as exc:
            errors = [f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()]
            return FlowValidationResult(
                is_valid=False,
                errors=errors,
                warnings=[],
                summary="Flow definition payload is invalid.",
                reason_codes=["flow_authoring.validation_failed"],
            )

        errors: list[str] = []
        warnings: list[str] = []
        node_ids = [node.node_id for node in resolved.nodes]
        edge_ids = [edge.edge_id for edge in resolved.edges]
        allowed_kinds = {"start", "card", "branch", "merge", "final"}

        if len(set(node_ids)) != len(node_ids):
          errors.append("node ids must be unique")
        if len(set(edge_ids)) != len(edge_ids):
          errors.append("edge ids must be unique")
        if sum(1 for node in resolved.nodes if node.kind == "start") != 1:
          errors.append("exactly one start node is required")
        if sum(1 for node in resolved.nodes if node.kind == "final") != 1:
          errors.append("exactly one final node is required")

        for node in resolved.nodes:
            if node.kind not in allowed_kinds:
                errors.append(f"unsupported node kind '{node.kind}'")
            if node.kind == "card" and not str(node.assigned_card_id or "").strip():
                errors.append(f"card node '{node.node_id}' requires assigned_card_id")

        known_nodes = set(node_ids)
        for edge in resolved.edges:
            if edge.from_node_id not in known_nodes:
                errors.append(f"edge '{edge.edge_id}' references unknown from_node_id '{edge.from_node_id}'")
            if edge.to_node_id not in known_nodes:
                errors.append(f"edge '{edge.edge_id}' references unknown to_node_id '{edge.to_node_id}'")

        if any(node.kind in {"branch", "merge"} for node in resolved.nodes):
            warnings.append("Branch and merge nodes are persisted, but run initiation remains a bounded single-card slice.")

        return FlowValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            summary="Flow definition payload is valid." if len(errors) == 0 else "Flow definition payload is invalid.",
            reason_codes=["flow_authoring.valid"] if len(errors) == 0 else ["flow_authoring.validation_failed"],
        )

    async def prepare_flow_run(self, *, flow_id: str, expected_revision_id: str | None = None) -> tuple[str, str]:
        flow_detail = await self.get_flow(flow_id)
        revision_id = str(flow_detail.get("revision_id") or "")
        if expected_revision_id and revision_id and expected_revision_id != revision_id:
            raise FlowAuthoringConflictError(
                f"revision_conflict: expected '{expected_revision_id}' but found '{revision_id}'"
            )

        validation = self.validate_definition(
            {
                "name": flow_detail["name"],
                "description": flow_detail["description"],
                "nodes": flow_detail["nodes"],
                "edges": flow_detail["edges"],
            }
        )
        if not validation.is_valid:
            raise FlowRuntimeNotAdmittedError("flow_validation_failed")

        nodes = [FlowNodeWriteModel.model_validate(node) for node in flow_detail["nodes"]]
        card_nodes = [node for node in nodes if node.kind == "card"]
        if len(card_nodes) != 1:
            raise FlowRuntimeNotAdmittedError("current_flow_run_slice_requires_exactly_one_card_node")
        if any(node.kind in {"branch", "merge"} for node in nodes):
            raise FlowRuntimeNotAdmittedError("current_flow_run_slice_does_not_admit_branch_or_merge")

        assigned_card_id = str(card_nodes[0].assigned_card_id or "").strip()
        if not assigned_card_id:
            raise FlowRuntimeNotAdmittedError("card_node_missing_assigned_card_id")

        return revision_id, assigned_card_id
