from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


def args_hash(args: dict[str, Any]) -> str:
    """The existing outward v1 argument digest recipe, shared by all its consumers."""
    payload = json.dumps(args, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def outward_attempt_id(run_id: str, execution_generation: int) -> str:
    return f"outward:{run_id}:generation:{execution_generation}"


@dataclass(frozen=True)
class OutwardAuthorization:
    proposal_id: str
    run_id: str
    execution_generation: int
    turn: int
    step_index: int
    namespace: str
    workspace_root: str
    target_ref: str
    tool: str
    connector_version: str
    arguments_json: str
    arguments_digest: str
    policy_json: str
    policy_digest: str
    submitted_at: str
    expires_at: str
    schema_version: str = "outward_authorization.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "outward_authorization.v1" or self.execution_generation < 1:
            raise ValueError("E_OUTWARD_AUTHORIZATION_VERSION")
        if self.turn < 0 or self.step_index < 0:
            raise ValueError("E_OUTWARD_AUTHORIZATION_POSITION")
        if not all((self.proposal_id, self.run_id, self.namespace, self.workspace_root,
                    self.target_ref, self.tool, self.connector_version, self.submitted_at, self.expires_at)):
            raise ValueError("E_OUTWARD_AUTHORIZATION_INCOMPLETE")
        for payload, digest in ((self.arguments_json, self.arguments_digest), (self.policy_json, self.policy_digest)):
            value = json.loads(payload)
            if not isinstance(value, dict) or canonical_json(value) != payload:
                raise ValueError("E_OUTWARD_AUTHORIZATION_NONCANONICAL")
            if args_hash(value) != digest:
                raise ValueError("E_OUTWARD_AUTHORIZATION_INPUT_DIGEST")

    @property
    def arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments_json)

    @property
    def digest(self) -> str:
        return args_hash(asdict(self))

    @property
    def effect_id(self) -> str:
        return f"outward-effect:{self.proposal_id}"

    @property
    def attempt_id(self) -> str:
        return outward_attempt_id(self.run_id, self.execution_generation)

    def to_json(self) -> str:
        return canonical_json(asdict(self))

    @classmethod
    def from_json(cls, payload: str, digest: str) -> OutwardAuthorization:
        binding = cls(**json.loads(payload))
        if binding.digest != digest:
            raise ValueError("E_OUTWARD_AUTHORIZATION_DIGEST")
        return binding
