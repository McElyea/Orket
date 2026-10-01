"""Run epic workspace setup once, before approval-resumable card dispatch."""

from orket.application.services import orchestrator_runtime_policy as orchestrator_policy
from orket.application.services.dependency_manager import DependencyValidationError
from orket.application.services.deployment_planner import DeploymentValidationError
from orket.application.services.scaffolder import ScaffoldValidationError
from orket.exceptions import ExecutionFailed
from orket.logging import log_event


async def prepare_epic_workspace(owner, epic, run_id):
    stages = (
        (
            "scaffolder",
            "Scaffolder",
            lambda: orchestrator_policy.select_bool_flag(
                "ORKET_DISABLE_SCAFFOLDER",
                "disable_scaffolder",
                process_rules=orchestrator_policy.organization_process_rules(owner.org),
            ),
            lambda **kwargs: owner.support_services.create_scaffolder(**kwargs),
            ScaffoldValidationError,
            ("created_directories", "created_files"),
        ),
        (
            "dependency_manager",
            "Dependency manager",
            lambda: orchestrator_policy.select_bool_flag(
                "ORKET_DISABLE_DEPENDENCY_MANAGER",
                "disable_dependency_manager",
                process_rules=orchestrator_policy.organization_process_rules(owner.org),
            ),
            lambda **kwargs: owner.support_services.create_dependency_manager(**kwargs),
            DependencyValidationError,
            ("created_files",),
        ),
        (
            "deployment_planner",
            "Deployment planner",
            lambda: orchestrator_policy.select_bool_flag(
                "ORKET_DISABLE_DEPLOYMENT_PLANNER",
                "disable_deployment_planner",
                process_rules=orchestrator_policy.organization_process_rules(owner.org),
            ),
            lambda **kwargs: owner.support_services.create_deployment_planner(**kwargs),
            DeploymentValidationError,
            ("created_files",),
        ),
    )
    for name, label, disabled, create, validation_error, counts in stages:
        identity = {"run_id": run_id, "epic": epic.name}
        if disabled():
            log_event(name + "_skipped_policy", identity, owner.workspace)
            continue
        log_event(name + "_started", identity, owner.workspace)
        service = create(
            workspace_root=owner.workspace,
            organization=owner.org,
            project_surface_profile=orchestrator_policy.select_project_surface_profile(
                user_settings=owner.support_services.load_user_settings(),
                process_rules=orchestrator_policy.organization_process_rules(owner.org),
            ),
            architecture_pattern=orchestrator_policy.select_architecture_pattern(
                orchestrator_policy.select_architecture_mode(
                    user_settings=owner.support_services.load_user_settings(),
                    process_rules=orchestrator_policy.organization_process_rules(owner.org),
                    environment=owner.decision_environment,
                    architecture_policy=owner.architecture_policy,
                )
            ),
        )
        try:
            result = await service.ensure()
        except validation_error as exc:
            log_event(name + "_failed", {**identity, "error": str(exc)}, owner.workspace)
            raise ExecutionFailed(f"{label} validation failed: {exc}") from exc
        log_event(
            name + "_completed", {**identity, **{key: len(result.get(key, [])) for key in counts}}, owner.workspace
        )
