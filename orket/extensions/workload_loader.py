from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path
from typing import Any, Callable

from orket_extension_sdk.result import WorkloadResult
from orket_extension_sdk.workload import Workload as SDKWorkload
from orket_extension_sdk.workload import WorkloadContext as SDKWorkloadContext

from .contracts import ExtensionRegistry, Workload
from .models import ExtensionRecord, WorkloadRecord


class WorkloadLoader:
    """Loads legacy and SDK workloads from extension sources."""

    def __init__(self, registry_factory: Callable[[], ExtensionRegistry]) -> None:
        self.registry_factory = registry_factory

    def load_legacy_workload(self, extension: ExtensionRecord, workload_id: str) -> Workload:
        extension_path = Path(extension.path).resolve()
        if not extension_path.exists():
            raise FileNotFoundError(f"Extension path missing: {extension.path}")
        self.validate_extension_imports(extension_path, extension.module)

        added_path = False
        if str(extension_path) not in sys.path:
            sys.path.insert(0, str(extension_path))
            added_path = True
        try:
            module = importlib.import_module(extension.module)
            register = getattr(module, extension.register_callable, None)
            if register is None or not callable(register):
                raise ValueError(
                    f"Register callable '{extension.register_callable}' not found in module '{extension.module}'"
                )
            registry = self.registry_factory()
            register(registry)
            workloads = registry.workloads()
            workload = workloads.get(workload_id)
            if workload is None:
                raise ValueError(f"Extension '{extension.extension_id}' does not register workload '{workload_id}'")
            return workload
        finally:
            if added_path:
                try:
                    sys.path.remove(str(extension_path))
                except ValueError:
                    pass

    def load_sdk_workload(self, extension: ExtensionRecord, workload: WorkloadRecord) -> SDKWorkload:
        extension_path = Path(extension.path).resolve()
        if not extension_path.exists():
            raise FileNotFoundError(f"Extension path missing: {extension.path}")
        module_name, attr_name = self.parse_sdk_entrypoint(workload.entrypoint)
        self.validate_extension_imports(extension_path, module_name)

        added_path = False
        if str(extension_path) not in sys.path:
            sys.path.insert(0, str(extension_path))
            added_path = True
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, attr_name, None)
            if target is None:
                raise ValueError(f"E_SDK_ENTRYPOINT_MISSING: {workload.entrypoint}")
            if inspect.isclass(target):
                instance = target()
            elif callable(target) and hasattr(target, "run"):
                instance = target
            elif callable(target):

                class _CallableWorkload:
                    def __init__(self, func: Callable[[SDKWorkloadContext, dict[str, Any]], WorkloadResult]) -> None:
                        self._func = func

                    def run(self, ctx: SDKWorkloadContext, payload: dict[str, Any]) -> WorkloadResult:
                        return self._func(ctx, payload)

                instance = _CallableWorkload(target)
            else:
                raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {workload.entrypoint}")

            run_method = getattr(instance, "run", None)
            if run_method is None or not callable(run_method):
                raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {workload.entrypoint}")
            return instance
        finally:
            if added_path:
                try:
                    sys.path.remove(str(extension_path))
                except ValueError:
                    pass

    @staticmethod
    def parse_sdk_entrypoint(entrypoint: str) -> tuple[str, str]:
        value = str(entrypoint or "").strip()
        module_name, sep, attr_name = value.partition(":")
        if sep != ":" or not module_name.strip() or not attr_name.strip():
            raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {entrypoint}")
        return module_name.strip(), attr_name.strip()

    @staticmethod
    def validate_extension_imports(extension_path: Path, module_name: str) -> None:
        module_path = extension_path / Path(*module_name.split("."))
        file_path = module_path.with_suffix(".py")
        package_init_path = module_path / "__init__.py"
        if file_path.exists():
            source_path = file_path
        elif package_init_path.exists():
            source_path = package_init_path
        else:
            raise FileNotFoundError(f"Extension module source not found for '{module_name}' under {extension_path}")

        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))
        blocked_prefixes = (
            "orket.orchestration",
            "orket.decision_nodes",
            "orket.runtime",
            "orket.application",
            "orket.adapters",
            "orket.interfaces",
            "orket.services",
            "orket.kernel",
            "orket.core",
            "orket.webhook_server",
            "orket.orket",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = str(alias.name or "")
                    if name.startswith("orket.") and not name.startswith("orket.extensions"):
                        if any(name.startswith(prefix) for prefix in blocked_prefixes):
                            raise ValueError(f"Extension import blocked by isolation policy: {name}")
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                if module.startswith("orket.") and not module.startswith("orket.extensions"):
                    if any(module.startswith(prefix) for prefix in blocked_prefixes):
                        raise ValueError(f"Extension import blocked by isolation policy: {module}")
