"""Capture sandbox strategy context and retain allocation cleanup ownership."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.decision_inputs import SandboxComposeInput, SandboxPortInput
from orket.core.domain.sandbox import PortAllocator, Sandbox, TechStack


@dataclass(frozen=True)
class SandboxCreationInputs:
    created_at: str
    policy: Any = field(repr=False)
    db_password: str = field(repr=False)
    admin_password: str = field(repr=False)


def capture_sandbox_creation(runtime_inputs: RuntimeInputService, policy: Any) -> SandboxCreationInputs:
    return SandboxCreationInputs(created_at=runtime_inputs.utc_now_iso(), policy=policy,
        db_password=runtime_inputs.create_secret_token(), admin_password=runtime_inputs.create_secret_token())


def admit_sandbox_text(value: Any, field_name: str) -> str:
    if type(value) is not str:
        raise ValueError("E_SANDBOX_POLICY_INVALID_" + field_name.upper())
    return value


def allocate_sandbox(*, allocator: PortAllocator, inputs: SandboxCreationInputs, sandbox_id: str,
                     rock_id: str, project_name: str, tech_stack: TechStack, workspace_path: str) -> Sandbox:
    ports = allocator.allocate(sandbox_id, tech_stack)
    admitted = False
    try:
        port_inputs = SandboxPortInput.model_validate(ports.model_dump())
        project = admit_sandbox_text(inputs.policy.build_compose_project(sandbox_id), "compose_project")
        database_url = admit_sandbox_text(inputs.policy.get_database_url(tech_stack.value, port_inputs,
                                                                        inputs.db_password), "database_url")
        sandbox = Sandbox(id=sandbox_id, rock_id=rock_id, project_name=project_name, tech_stack=tech_stack,
            ports=ports, compose_project=project, workspace_path=workspace_path, api_url=f"http://localhost:{ports.api}",
            frontend_url=f"http://localhost:{ports.frontend}", database_url=database_url,
            admin_url=f"http://localhost:{ports.admin_tool}" if ports.admin_tool else None, created_at=inputs.created_at)
        admitted = True
        return sandbox
    finally:
        if not admitted:
            allocator.release(sandbox_id)


def capture_sandbox_compose(sandbox: Sandbox) -> SandboxComposeInput:
    return SandboxComposeInput(id=sandbox.id, rock_id=sandbox.rock_id, tech_stack=sandbox.tech_stack.value,
                                ports=SandboxPortInput.model_validate(sandbox.ports.model_dump()))


def render_sandbox_compose(policy: Any, sandbox: Sandbox, db_password: str, admin_password: str) -> str:
    inputs = capture_sandbox_compose(sandbox)
    return admit_sandbox_text(policy.generate_compose_file(sandbox=inputs, db_password=db_password,
                                                          admin_password=admin_password), "compose_text")
