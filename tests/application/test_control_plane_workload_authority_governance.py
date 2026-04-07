# Layer: unit

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "orket",
    REPO_ROOT / "scripts",
)
WORKLOAD_AUTHORITY_MATRIX_DOC = (
    REPO_ROOT / "docs" / "projects" / "ControlPlane" / "CONTROL_PLANE_CONVERGENCE_WORKSTREAM_1_CLOSEOUT.md"
)
ALLOWED_PATHS = {
    REPO_ROOT / "orket" / "application" / "services" / "control_plane_workload_catalog.py",
    REPO_ROOT / "orket" / "core" / "contracts" / "workload_identity.py",
}
LOW_LEVEL_BUILDERS = {
    "_build_control_plane_workload_record",
    "_build_control_plane_workload_record_from_workload_contract",
}
WORKLOAD_AUTHORITY_IMPORTS = {
    "GITEA_STATE_WORKER_EXECUTION_WORKLOAD",
    "KERNEL_ACTION_WORKLOAD",
    "ORCHESTRATOR_CHILD_WORKLOAD_COMPOSITION_WORKLOAD",
    "ORCHESTRATOR_ISSUE_DISPATCH_WORKLOAD",
    "ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD",
    "REVIEW_RUN_WORKLOAD",
    "TURN_TOOL_WORKLOAD",
    "_resolve_extension_control_plane_workload",
    "_resolve_odr_arbiter_control_plane_workload_from_contract",
    "control_plane_workload_for_key",
    "resolve_cards_control_plane_workload_from_contract",
    "resolve_control_plane_workload",
    "sandbox_runtime_workload_for_tech_stack",
}
EXPECTED_GOVERNED_START_PATH_MATRIX = {
    "cards epic execution": {
        "status": "projection-resolved",
        "paths": {"orket/runtime/execution/epic_run_orchestrator.py"},
    },
    "atomic issue execution": {
        "status": "projection-resolved",
        "paths": {"orket/runtime/execution/epic_run_orchestrator.py"},
    },
    "ODR / run arbiter": {
        "status": "projection-resolved",
        "paths": {"scripts/odr/run_arbiter.py"},
    },
    "manual review-run": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/review_run_control_plane_service.py"},
    },
    "sandbox runtime": {
        "status": "catalog-resolved",
        "paths": {
            "orket/application/services/sandbox_control_plane_execution_service.py",
            "orket/services/sandbox_orchestrator.py",
        },
    },
    "kernel action": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/kernel_action_control_plane_service.py"},
    },
    "governed turn-tool": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/turn_tool_control_plane_service.py"},
    },
    "orchestrator issue dispatch": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_issue_control_plane_service.py"},
    },
    "orchestrator scheduler mutation": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_scheduler_control_plane_service.py"},
    },
    "orchestrator child workload composition": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/orchestrator_scheduler_control_plane_service.py"},
    },
    "Gitea state worker": {
        "status": "catalog-resolved",
        "paths": {"orket/application/services/gitea_state_control_plane_execution_service.py"},
    },
    "extension workload execution": {
        "status": "projection-resolved",
        "paths": {"orket/extensions/manager.py"},
    },
    "rock entrypoints that initiate governed execution": {
        "status": "routing-only",
        "paths": set(),
    },
}
CATALOG_RESOLVED_IDENTITY_ALIAS_BANS = {
    "orket/application/services/gitea_state_control_plane_execution_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/kernel_action_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/orchestrator_issue_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/orchestrator_scheduler_control_plane_service.py": {
        "TRANSITION_WORKLOAD_ID",
        "TRANSITION_WORKLOAD_VERSION",
        "CHILD_WORKLOAD_ID",
        "CHILD_WORKLOAD_VERSION",
    },
    "orket/application/services/review_run_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
    "orket/application/services/turn_tool_control_plane_service.py": {
        "WORKLOAD_ID",
        "WORKLOAD_VERSION",
    },
}
COMPATIBILITY_WRAPPER_CALLS = {"run_epic", "run_issue", "run_rock"}
ALLOWED_COMPATIBILITY_WRAPPER_CALLERS = {
    "orket/interfaces/cli.py": {"run_epic"},
}
EXTENSION_MANIFEST_WORKLOAD_ALIAS = "WorkloadRecord"
EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR = "ExtensionManifestWorkload"
PRIVATE_EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR = "_ExtensionManifestEntry"
RETIRED_EXTENSION_WORKLOAD_DESCRIPTOR = "ExtensionWorkloadDescriptor"
PRIVATE_CATALOG_HELPER_IMPORT_OWNERS = {
    "_resolve_extension_control_plane_workload": {"orket/extensions/manager.py"},
    "_resolve_odr_arbiter_control_plane_workload_from_contract": {"scripts/odr/run_arbiter.py"},
}
PRIVATE_EXTENSION_MANIFEST_IMPORT_OWNERS = {
    "orket/extensions/artifact_provenance.py",
    "orket/extensions/catalog.py",
    "orket/extensions/manager.py",
    "orket/extensions/manifest_parser.py",
    "orket/extensions/sdk_workload_runner.py",
    "orket/extensions/workload_executor.py",
    "orket/extensions/workload_loader.py",
}
RUNTIME_PIPELINE_METHOD_OWNERS = (
    (REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline.py", "ExecutionPipeline"),
    (
        REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_artifact_provenance.py",
        "ExecutionPipelineArtifactProvenanceMixin",
    ),
    (
        REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_card_dispatch.py",
        "ExecutionPipelineCardDispatchMixin",
    ),
    (
        REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_ledger_events.py",
        "ExecutionPipelineLedgerEventsMixin",
    ),
    (REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_resume.py", "ExecutionPipelineResumeMixin"),
    (
        REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_run_summary.py",
        "ExecutionPipelineRunSummaryMixin",
    ),
    (
        REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_runtime_artifacts.py",
        "ExecutionPipelineRuntimeArtifactsMixin",
    ),
)


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def _relative_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _builder_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported = sorted(
                alias.name
                for alias in node.names
                if alias.name in LOW_LEVEL_BUILDERS
            )
            if imported:
                violations.append(f"import:{','.join(imported)}")
            continue
        if isinstance(node, ast.Call):
            target = ""
            if isinstance(node.func, ast.Name):
                target = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target = node.func.attr
            if target in LOW_LEVEL_BUILDERS:
                violations.append(f"call:{target}")
    return sorted(set(violations))


def _parse_workload_authority_matrix() -> dict[str, str]:
    text = WORKLOAD_AUTHORITY_MATRIX_DOC.read_text(encoding="utf-8")
    start_marker = "The current workload-authority matrix for governed start paths is:"
    end_marker = "## Surviving projection-only or still-temporary surfaces"
    section = text.split(start_marker, 1)[1].split(end_marker, 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        parts = [part.strip() for part in stripped.strip("|").split("|")]
        if len(parts) != 3:
            continue
        start_path, status, truthful_note = parts
        if start_path == "Start path" or start_path == "---" or status == "---" or truthful_note == "---":
            continue
        rows[start_path] = status.strip("`")
    return rows


def _catalog_authority_consumer_paths() -> set[str]:
    consumers: set[str] = set()
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "orket.application.services.control_plane_workload_catalog":
                continue
            imported = {alias.name for alias in node.names}
            if imported & WORKLOAD_AUTHORITY_IMPORTS:
                consumers.add(_relative_path(path))
                break
    return consumers


def _import_violations(*, module_names: set[str], imported_names: set[str] | None = None) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for path in _iter_python_files():
        relative_path = _relative_path(path)
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        hits: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if str(alias.name or "") in module_names:
                        hits.append(f"import:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module in module_names:
                    imported = {alias.name for alias in node.names}
                    if imported_names is None:
                        hits.append(f"from:{module}")
                    else:
                        matched = sorted(imported & imported_names)
                        if matched:
                            hits.extend(f"from:{module}:{name}" for name in matched)
        if hits:
            violations[relative_path] = sorted(set(hits))
    return violations


def _named_importers(
    *,
    module_name: str,
    imported_name: str,
    relative_module_name: str | None = None,
    required_path_prefix: str | None = None,
) -> set[str]:
    importers: set[str] = set()
    for path in _iter_python_files():
        relative_path = _relative_path(path)
        if required_path_prefix is not None and not relative_path.startswith(required_path_prefix):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            node_module = str(node.module or "")
            is_named_module = node_module == module_name
            is_relative_module = (
                relative_module_name is not None
                and node.level > 0
                and node_module == relative_module_name
            )
            if not (is_named_module or is_relative_module):
                continue
            if any(alias.name == imported_name for alias in node.names):
                importers.add(relative_path)
                break
    return importers


def _load_execution_pipeline_method(method_name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for path, class_name in RUNTIME_PIPELINE_METHOD_OWNERS:
        try:
            return _load_class_method(path, class_name=class_name, method_name=method_name)
        except AssertionError:
            continue
    raise AssertionError(f"Runtime pipeline method {method_name} not found")


def _load_class_method(path: Path, *, class_name: str, method_name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)) and child.name == method_name:
                return child
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def _class_has_method(path: Path, *, class_name: str, method_name: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for child in node.body:
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)) and child.name == method_name:
                return True
    return False


def _runtime_pipeline_has_method(method_name: str) -> bool:
    return any(
        _class_has_method(path, class_name=class_name, method_name=method_name)
        for path, class_name in RUNTIME_PIPELINE_METHOD_OWNERS
    )


def _load_module_function(path: Path, *, function_name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == function_name:
            return node
    raise AssertionError(f"{function_name} not found in {path}")


def _module_all_exports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    exports: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        for elt in node.value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                exports.add(elt.value)
    return exports


def _class_assignment_targets(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if not isinstance(child, ast.Assign):
                continue
            for target in child.targets:
                if isinstance(target, ast.Name):
                    targets.add(target.id)
    return targets


def _call_targets(node: ast.AST) -> set[str]:
    targets: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            targets.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            targets.add(child.func.attr)
    return targets


def test_only_workload_authority_seam_mints_control_plane_workload_records() -> None:
    violations: dict[str, list[str]] = {}
    for path in _iter_python_files():
        if path in ALLOWED_PATHS:
            continue
        hits = _builder_violations(path)
        if hits:
            violations[_relative_path(path)] = hits
    assert violations == {}


def test_governed_start_path_matrix_stays_classified_and_exact() -> None:
    matrix = _parse_workload_authority_matrix()
    expected_statuses = {
        start_path: meta["status"] for start_path, meta in EXPECTED_GOVERNED_START_PATH_MATRIX.items()
    }
    assert matrix == expected_statuses


def test_only_matrix_covered_modules_consume_catalog_workload_authority() -> None:
    expected_paths = {
        path
        for meta in EXPECTED_GOVERNED_START_PATH_MATRIX.values()
        for path in meta["paths"]
    }
    assert _catalog_authority_consumer_paths() == expected_paths


def test_catalog_resolved_publishers_do_not_restate_workload_identity_as_string_aliases() -> None:
    violations = {
        relative_path: sorted(
            _class_assignment_targets(REPO_ROOT / relative_path) & banned_assignments
        )
        for relative_path, banned_assignments in CATALOG_RESOLVED_IDENTITY_ALIAS_BANS.items()
        if _class_assignment_targets(REPO_ROOT / relative_path) & banned_assignments
    }
    assert violations == {}


def test_rock_entrypoints_remain_routing_only_retirement_debt() -> None:
    """Layer: unit. Verifies internal rock routing stays routing-only through the generic epic-collection entry."""
    call_targets = _call_targets(_load_execution_pipeline_method("_run_epic_collection_entry"))

    assert "run_card" in call_targets
    assert {
        "_build_control_plane_workload_record",
        "_build_control_plane_workload_record_from_workload_contract",
        "control_plane_workload_for_key",
        "resolve_control_plane_workload",
        "sandbox_runtime_workload_for_tech_stack",
    }.isdisjoint(call_targets)


def test_runtime_epic_collection_entry_no_longer_returns_rock_shaped_payload() -> None:
    """Layer: unit. Verifies the internal collection path emits collection-shaped runtime output."""
    method = _load_execution_pipeline_method("_run_epic_collection_entry")
    return_keys: set[str] = set()

    for node in ast.walk(method):
        if not isinstance(node, ast.Return):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for key in node.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                return_keys.add(key.value)

    assert "rock" not in return_keys
    assert {"collection", "results"} <= return_keys


def test_no_non_test_runtime_path_calls_compatibility_wrappers() -> None:
    violations = {}
    for path in _iter_python_files():
        relative_path = _relative_path(path)
        hits = _call_targets(ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))) & COMPATIBILITY_WRAPPER_CALLS
        hits -= ALLOWED_COMPATIBILITY_WRAPPER_CALLERS.get(relative_path, set())
        if hits:
            violations[relative_path] = sorted(hits)

    assert violations == {}


def test_workload_adapter_shim_is_retired_and_has_no_non_test_importers() -> None:
    """Layer: unit. Verifies the former runtime workload-adapter shim stays deleted and repo code does not reintroduce imports."""
    workload_adapter_path = REPO_ROOT / "orket" / "runtime" / "workload_adapters.py"
    violations = _import_violations(module_names={"orket.runtime.workload_adapters"})

    assert workload_adapter_path.exists() is False
    assert violations == {}


def test_non_test_repo_code_does_not_import_extension_manifest_workload_alias() -> None:
    violations = _import_violations(
        module_names={"orket.extensions.models", "orket.extensions"},
        imported_names={EXTENSION_MANIFEST_WORKLOAD_ALIAS},
    )

    assert violations == {}


def test_core_contracts_do_not_reexport_private_workload_builders() -> None:
    core_contracts_init = (REPO_ROOT / "orket" / "core" / "contracts" / "__init__.py").read_text(encoding="utf-8-sig")

    assert "_build_control_plane_workload_record" not in core_contracts_init
    assert "_build_control_plane_workload_record_from_workload_contract" not in core_contracts_init


def test_catalog_private_helpers_are_not_blessed_in_dunder_all() -> None:
    """Layer: unit. Verifies catalog-local helper seams stay internal-only and are not exported as public module surface."""
    exports = _module_all_exports(REPO_ROOT / "orket" / "application" / "services" / "control_plane_workload_catalog.py")

    assert "_resolve_extension_control_plane_workload" not in exports


def test_private_catalog_helpers_have_only_exact_runtime_owner_importers() -> None:
    """Layer: unit. Verifies private catalog helpers are consumed only by their exact runtime owner paths."""
    for helper_name, expected_importers in PRIVATE_CATALOG_HELPER_IMPORT_OWNERS.items():
        assert _named_importers(
            module_name="orket.application.services.control_plane_workload_catalog",
            imported_name=helper_name,
        ) == expected_importers


def test_extensions_package_root_does_not_reexport_manifest_workload_alias() -> None:
    """Layer: unit. Verifies package-root extension exports do not bless manifest workload metadata nouns."""
    extensions_init = (REPO_ROOT / "orket" / "extensions" / "__init__.py").read_text(encoding="utf-8-sig")
    exports = _module_all_exports(REPO_ROOT / "orket" / "extensions" / "__init__.py")

    assert "WorkloadRecord" not in extensions_init
    assert EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR not in exports


def test_extension_manager_dunder_all_does_not_bless_manifest_workload_descriptor() -> None:
    """Layer: unit. Verifies manager-module exports do not bless manifest workload metadata nouns."""
    exports = _module_all_exports(REPO_ROOT / "orket" / "extensions" / "manager.py")

    assert EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR not in exports


def test_extension_manager_module_does_not_expose_manifest_workload_descriptor() -> None:
    """Layer: unit. Verifies manager module no longer exposes manifest workload metadata as a runtime attribute."""
    import importlib

    manager_module = importlib.import_module("orket.extensions.manager")

    assert not hasattr(manager_module, EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR)


def test_extension_manager_class_no_longer_exposes_generic_workload_lookup() -> None:
    """Layer: unit. Verifies manifest metadata lookup is no longer blessed as a generic public workload surface."""
    manager_path = REPO_ROOT / "orket" / "extensions" / "manager.py"

    assert _class_has_method(manager_path, class_name="ExtensionManager", method_name="resolve_workload") is False
    assert _class_has_method(manager_path, class_name="ExtensionManager", method_name="has_manifest_entry") is True
    assert _class_has_method(manager_path, class_name="ExtensionManager", method_name="uses_sdk_contract") is True
    assert _class_has_method(manager_path, class_name="ExtensionManager", method_name="_resolve_manifest_workload") is False
    assert _class_has_method(manager_path, class_name="ExtensionManager", method_name="_resolve_manifest_entry") is True


def test_extension_catalog_no_longer_exposes_public_manifest_lookup() -> None:
    """Layer: unit. Verifies manifest metadata lookup stays internal to the extension catalog surface."""
    catalog_path = REPO_ROOT / "orket" / "extensions" / "catalog.py"

    assert _class_has_method(catalog_path, class_name="ExtensionCatalog", method_name="resolve_manifest_entry") is False
    assert _class_has_method(catalog_path, class_name="ExtensionCatalog", method_name="_resolve_manifest_entry") is True


def test_sessions_router_uses_manifest_presence_probe_instead_of_metadata_lookup() -> None:
    """Layer: unit. Verifies interaction session routing validates extension workload ids through a boolean probe."""
    router_text = (REPO_ROOT / "orket" / "interfaces" / "routers" / "sessions.py").read_text(encoding="utf-8-sig")

    assert ".has_manifest_entry(" in router_text
    assert ".resolve_workload(" not in router_text


def test_controller_dispatcher_uses_manager_sdk_probe_instead_of_private_manifest_tuple() -> None:
    """Layer: unit. Verifies controller dispatch uses boolean manager probes instead of resolving private manifest metadata."""
    dispatcher_text = (REPO_ROOT / "orket" / "extensions" / "controller_dispatcher.py").read_text(
        encoding="utf-8-sig"
    )

    assert ".has_manifest_entry(" in dispatcher_text
    assert ".uses_sdk_contract(" in dispatcher_text
    assert "._resolve_manifest_entry(" not in dispatcher_text


def test_extension_models_do_not_define_manifest_workload_alias() -> None:
    import importlib
    from dataclasses import fields

    extension_models = (REPO_ROOT / "orket" / "extensions" / "models.py").read_text(encoding="utf-8-sig")
    models_module = importlib.import_module("orket.extensions.models")
    field_names = {field.name for field in fields(models_module.ExtensionRecord)}

    assert "WorkloadRecord =" not in extension_models
    assert f"class {EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR}" not in extension_models
    assert f"class {PRIVATE_EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR}" in extension_models
    assert f"class {RETIRED_EXTENSION_WORKLOAD_DESCRIPTOR}" not in extension_models
    assert not hasattr(models_module, EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR)
    assert hasattr(models_module, PRIVATE_EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR)
    assert "workloads" not in field_names
    assert "manifest_workloads" not in field_names
    assert "manifest_entries" in field_names


def test_extension_catalog_persisted_rows_use_manifest_entries_key() -> None:
    """Layer: unit. Verifies installed extension catalog serialization no longer emits a generic workloads key."""
    import importlib

    catalog_module = importlib.import_module("orket.extensions.catalog")
    models_module = importlib.import_module("orket.extensions.models")
    manifest_entry = getattr(models_module, PRIVATE_EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR)(
        workload_id="demo_v1",
        workload_version="1.0.0",
        entrypoint="demo:run",
        required_capabilities=("workspace.root",),
        contract_style="sdk_v0",
    )
    record = models_module.ExtensionRecord(
        extension_id="demo.ext",
        extension_version="1.0.0",
        source="git+demo",
        extension_api_version="1.0.0",
        path="demo",
        module="demo_module",
        register_callable="register",
        manifest_entries=(manifest_entry,),
        contract_style="sdk_v0",
        manifest_path="demo/extension.yaml",
        resolved_commit_sha="a" * 40,
        manifest_digest_sha256="b" * 64,
        source_ref="HEAD",
        trust_profile="production",
        installed_at_utc="2026-03-29T00:00:00Z",
        security_mode="compat",
        security_profile="production",
        security_policy_version="c" * 64,
        compat_fallbacks=(),
    )

    row = catalog_module.ExtensionCatalog.row_from_record(record)

    assert "manifest_entries" in row
    assert "workloads" not in row


def test_private_extension_manifest_type_is_only_imported_inside_extensions_package() -> None:
    """Layer: unit. Verifies the private manifest metadata type does not escape extension-internal production code."""
    assert _named_importers(
        module_name="orket.extensions.models",
        imported_name=PRIVATE_EXTENSION_MANIFEST_WORKLOAD_DESCRIPTOR,
        relative_module_name="models",
        required_path_prefix="orket/extensions/",
    ) == PRIVATE_EXTENSION_MANIFEST_IMPORT_OWNERS


def test_public_runtime_wrappers_collapse_to_run_card() -> None:
    """Layer: unit. Verifies public runtime compatibility wrappers delegate to run_card instead of owning dispatch."""
    engine_issue_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "orchestration" / "engine.py",
            class_name="OrchestrationEngine",
            method_name="run_issue",
        )
    )
    engine_epic_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "orchestration" / "engine.py",
            class_name="OrchestrationEngine",
            method_name="run_epic",
        )
    )
    engine_rock_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "orchestration" / "engine.py",
            class_name="OrchestrationEngine",
            method_name="run_rock",
        )
    )
    pipeline_issue_targets = _call_targets(_load_execution_pipeline_method("run_issue"))
    pipeline_epic_targets = _call_targets(_load_execution_pipeline_method("run_epic"))
    pipeline_rock_targets = _call_targets(_load_execution_pipeline_method("run_rock"))
    pipeline_card_targets = _call_targets(_load_execution_pipeline_method("run_card"))
    gitea_loop_targets = _call_targets(_load_execution_pipeline_method("run_gitea_state_loop"))
    gitea_loop_worker_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "runtime" / "execution" / "gitea_state_loop.py",
            class_name="GiteaStateLoopRunner",
            method_name="_work_claimed_card",
        )
    )
    organization_loop_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "organization_loop.py",
            class_name="OrganizationLoop",
            method_name="run_forever",
        )
    )
    webhook_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "adapters" / "vcs" / "gitea_webhook_handlers.py",
            class_name="PRLifecycleHandler",
            method_name="handle_pr_opened",
        )
    )
    extension_runtime_targets = _call_targets(
        _load_class_method(
            REPO_ROOT / "orket" / "extensions" / "runtime.py",
            class_name="ExtensionEngineAdapter",
            method_name="execute_action",
        )
    )
    runtime_orchestrate_targets = _call_targets(
        _load_module_function(
            REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline.py",
            function_name="orchestrate",
        )
    )
    cli_targets = _call_targets(
        _load_module_function(
            REPO_ROOT / "orket" / "interfaces" / "cli.py",
            function_name="run_cli",
        )
    )

    assert engine_issue_targets == {"run_card"}
    assert engine_epic_targets == {"run_card"}
    assert engine_rock_targets == {"run_card"}
    assert pipeline_issue_targets == {"run_card"}
    assert pipeline_epic_targets == {"run_card"}
    assert pipeline_rock_targets == {"run_card"}
    assert {"_resolve_run_card_target", "_run_issue_entry", "_run_epic_entry", "_run_epic_collection_entry"} <= pipeline_card_targets
    assert {
        "resolve_control_plane_workload",
        "_build_control_plane_workload_record",
        "_build_control_plane_workload_record_from_workload_contract",
        "control_plane_workload_for_key",
        "build_cards_workload_contract",
    }.isdisjoint(pipeline_card_targets)
    assert "run_card" in extension_runtime_targets
    assert {"run_epic", "run_issue", "run_rock"}.isdisjoint(extension_runtime_targets)
    assert "run_card" in runtime_orchestrate_targets
    assert {"run_epic", "run_issue", "run_rock"}.isdisjoint(runtime_orchestrate_targets)
    assert "run_card" in cli_targets
    assert "run_epic" in cli_targets
    assert "run_rock" not in cli_targets
    assert "run_issue" not in cli_targets
    assert "run_gitea_state_loop" in gitea_loop_targets
    assert "run_card" in gitea_loop_worker_targets
    assert "run_issue" not in gitea_loop_targets
    assert "run_issue" not in gitea_loop_worker_targets
    assert "run_card" in organization_loop_targets
    assert "run_issue" not in organization_loop_targets
    assert "run_card" in webhook_targets
    assert "run_issue" not in webhook_targets


def test_extension_runtime_treats_run_rock_as_legacy_alias_not_primary_run_surface() -> None:
    """Layer: unit. Verifies the extension runtime adapter keeps `run_rock` only as explicit alias normalization."""
    extension_runtime_text = (REPO_ROOT / "orket" / "extensions" / "runtime.py").read_text(encoding="utf-8-sig")

    assert 'if op in {"run_card", "run_epic", "run_rock", "run_issue"}:' not in extension_runtime_text
    assert 'canonical_op = "run_card" if op in {"run_epic", "run_issue", "run_rock"} else op' in extension_runtime_text


def test_execution_pipeline_no_longer_assembles_cards_workload_authority_input_directly() -> None:
    """Layer: unit. Verifies the cards runtime path uses a catalog-local helper instead of assembling workload authority input locally."""
    execution_pipeline_text = (REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline.py").read_text(
        encoding="utf-8-sig"
    )
    card_dispatch_text = (REPO_ROOT / "orket" / "runtime" / "execution" / "execution_pipeline_card_dispatch.py").read_text(
        encoding="utf-8-sig"
    )
    epic_orchestrator_text = (REPO_ROOT / "orket" / "runtime" / "execution" / "epic_run_orchestrator.py").read_text(
        encoding="utf-8-sig"
    )

    assert "resolve_cards_control_plane_workload_from_contract" in epic_orchestrator_text
    assert "WorkloadAuthorityInput" not in execution_pipeline_text
    assert "WorkloadAuthorityInput" not in card_dispatch_text
    assert "WorkloadAuthorityInput" not in epic_orchestrator_text
    assert "resolve_control_plane_workload(" not in execution_pipeline_text
    assert "resolve_control_plane_workload(" not in card_dispatch_text
    assert "resolve_control_plane_workload(" not in epic_orchestrator_text


def test_extension_manager_no_longer_assembles_extension_workload_authority_input_directly() -> None:
    """Layer: unit. Verifies extension workload start uses a catalog-local helper instead of assembling workload authority input locally."""
    extension_manager_text = (REPO_ROOT / "orket" / "extensions" / "manager.py").read_text(
        encoding="utf-8-sig"
    )

    assert "_resolve_extension_control_plane_workload" in extension_manager_text
    assert "WorkloadAuthorityInput" not in extension_manager_text
    assert "resolve_control_plane_workload(" not in extension_manager_text


def test_run_arbiter_no_longer_assembles_odr_workload_authority_input_directly() -> None:
    """Layer: unit. Verifies the ODR arbiter uses a catalog-local helper instead of assembling workload authority input locally."""
    run_arbiter_text = (REPO_ROOT / "scripts" / "odr" / "run_arbiter.py").read_text(
        encoding="utf-8-sig"
    )

    assert "_resolve_odr_arbiter_control_plane_workload_from_contract" in run_arbiter_text
    assert "WorkloadAuthorityInput" not in run_arbiter_text
    assert "resolve_control_plane_workload(" not in run_arbiter_text


def test_runtime_and_engine_expose_only_thin_run_rock_wrappers() -> None:
    """Layer: unit. Verifies run_rock survives only as a thin legacy public wrapper over run_card."""
    engine_path = REPO_ROOT / "orket" / "orchestration" / "engine.py"

    assert _runtime_pipeline_has_method("run_rock") is True
    assert _class_has_method(engine_path, class_name="OrchestrationEngine", method_name="run_rock") is True
    assert _call_targets(_load_execution_pipeline_method("run_rock")) == {"run_card"}
    assert _call_targets(
        _load_class_method(
            engine_path,
            class_name="OrchestrationEngine",
            method_name="run_rock",
        )
    ) == {"run_card"}


def test_runtime_execution_pipeline_no_longer_exposes_rock_named_internal_entry() -> None:
    """Layer: unit. Verifies internal rock routing no longer survives as a rock-named helper."""
    assert _runtime_pipeline_has_method("_run_rock_entry") is False


def test_runtime_execution_pipeline_no_longer_exposes_orchestrate_rock_helper() -> None:
    """Layer: unit. Verifies the legacy module-level rock helper is retired entirely."""
    import importlib

    execution_pipeline_module = importlib.import_module("orket.runtime.execution_pipeline")

    assert not hasattr(execution_pipeline_module, "orchestrate_rock")


def test_live_rock_benchmark_runner_prefers_canonical_card_surface() -> None:
    """Layer: unit. Verifies live benchmark tooling uses the canonical card surface and card-mode benchmark metadata defaults."""
    benchmark_runner_text = (
        REPO_ROOT / "scripts" / "benchmarks" / "live_rock_benchmark_runner.py"
    ).read_text(encoding="utf-8-sig")
    benchmark_suite_text = (
        REPO_ROOT / "scripts" / "benchmarks" / "run_live_rock_benchmark_suite.py"
    ).read_text(encoding="utf-8-sig")

    assert '"--card"' in benchmark_runner_text
    assert '"--rock"' not in benchmark_runner_text
    assert "benchmark_live_rock_" not in benchmark_runner_text
    assert '"run_mode": "rock"' not in benchmark_runner_text
    assert 'default="live-rock"' not in benchmark_runner_text
    assert 'default="live-rock"' not in benchmark_suite_text
    assert "benchmark_live_collection_" in benchmark_runner_text
    assert '"run_mode": "card"' in benchmark_runner_text
    assert 'default="live-card"' in benchmark_runner_text
    assert 'default="live-card"' in benchmark_suite_text
