"""Run epic workspace setup once, before approval-resumable card dispatch."""
from orket.application.services.dependency_manager import DependencyValidationError
from orket.application.services.deployment_planner import DeploymentValidationError
from orket.application.services.scaffolder import ScaffoldValidationError
from orket.exceptions import ExecutionFailed
from orket.logging import log_event


async def prepare_epic_workspace(owner, epic, run_id):
    stages = (
        ("scaffolder", "Scaffolder", owner._is_scaffolder_disabled,
         lambda **kwargs: owner.support_services.create_scaffolder(**kwargs), ScaffoldValidationError,
         ("created_directories", "created_files")),
        ("dependency_manager", "Dependency manager", owner._is_dependency_manager_disabled,
         lambda **kwargs: owner.support_services.create_dependency_manager(**kwargs), DependencyValidationError,
         ("created_files",)),
        ("deployment_planner", "Deployment planner", owner._is_deployment_planner_disabled,
         lambda **kwargs: owner.support_services.create_deployment_planner(**kwargs), DeploymentValidationError,
         ("created_files",)),
    )
    for name, label, disabled, create, validation_error, counts in stages:
        identity = {"run_id": run_id, "epic": epic.name}
        if disabled():
            log_event(name + "_skipped_policy", identity, owner.workspace)
            continue
        log_event(name + "_started", identity, owner.workspace)
        service = create(workspace_root=owner.workspace, organization=owner.org,
                         project_surface_profile=owner._resolve_project_surface_profile(),
                         architecture_pattern=owner._resolve_architecture_pattern())
        try:
            result = await service.ensure()
        except validation_error as exc:
            log_event(name + "_failed", {**identity, "error": str(exc)}, owner.workspace)
            raise ExecutionFailed(f"{label} validation failed: {exc}") from exc
        log_event(name + "_completed", {**identity, **{key: len(result.get(key, [])) for key in counts}}, owner.workspace)
