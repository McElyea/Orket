from __future__ import annotations

import asyncio
import builtins
import importlib
import importlib.abc
import inspect
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from orket.extensions.import_guard import ExtensionImportGuard
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket.extensions.workload_loader import WorkloadLoader
from orket_extension_sdk.result import WorkloadResult
from orket_extension_sdk.workload import WorkloadContext

_BASE_ALLOWED_STDLIB_MODULES = {"__future__", "_io"}


class DeclaredStdlibImportHook(importlib.abc.MetaPathFinder):
    """Blocks undeclared stdlib imports requested directly by extension code."""

    def __init__(self, *, extension_root: Path, allowed_stdlib_modules: set[str]) -> None:
        self._extension_root = extension_root.resolve()
        self._allowed_stdlib_modules = set(allowed_stdlib_modules) | _BASE_ALLOWED_STDLIB_MODULES
        self._host_import_guard = ExtensionImportGuard()
        self._hook_path = Path(__file__).resolve()

    def find_spec(
        self,
        fullname: str,
        path: object | None,
        target: object | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del path, target
        self.validate_import(fullname)
        return None

    def validate_import(self, fullname: str) -> None:
        if self._direct_request_originates_from_extension() and self._host_import_guard.is_blocked(fullname):
            raise ImportError(
                "E_EXT_IMPORT_BLOCKED: "
                f"'{fullname}' is internal host runtime surface; use orket_extension_sdk contracts."
            )
        top_level = fullname.split(".", 1)[0]
        if top_level not in sys.stdlib_module_names:
            return
        if top_level in self._allowed_stdlib_modules:
            return
        if self._direct_request_originates_from_extension():
            raise ImportError(f"E_EXT_STDLIB_IMPORT_UNDECLARED: {top_level}")

    def _direct_request_originates_from_extension(self) -> bool:
        frame = sys._getframe()
        while frame is not None:
            filename = frame.f_code.co_filename
            frame = frame.f_back
            if not filename or filename.startswith("<"):
                continue
            candidate = Path(filename).resolve()
            if candidate == self._hook_path or _is_importlib_bootstrap_frame(candidate):
                continue
            return candidate.is_relative_to(self._extension_root)
        return False


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        sys.stderr.write("usage: sdk_workload_subprocess <request.json> <result.json>\n")
        return 2
    request_path = Path(args[0])
    result_path = Path(args[1])
    try:
        request = json.loads(request_path.read_bytes().decode("utf-8"))
        result = _run_request(request)
        result_path.write_bytes(json.dumps(result.model_dump(mode="json"), sort_keys=True).encode("utf-8"))
        return 0
    except Exception as exc:
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        traceback.print_exc(file=sys.stderr)
        return 1


def _run_request(request: dict[str, Any]) -> WorkloadResult:
    extension = dict(request["extension"])
    workload = dict(request["workload"])
    context = dict(request["context"])
    extension_root = Path(str(extension["path"])).resolve()
    entrypoint = str(workload["entrypoint"])
    module_name, attr_name = WorkloadLoader.parse_sdk_entrypoint(entrypoint)
    allowed_stdlib_modules = {
        str(item).split(".", 1)[0]
        for item in extension.get("allowed_stdlib_modules", [])
        if str(item).strip()
    }

    sys.path.insert(0, str(extension_root))
    sys.meta_path.insert(
        0,
        import_hook := DeclaredStdlibImportHook(
            extension_root=extension_root, allowed_stdlib_modules=allowed_stdlib_modules
        ),
    )
    builtins.__import__ = _guarded_import(import_hook, builtins.__import__)
    importlib.import_module = _guarded_import_module(import_hook, importlib.import_module)
    module = importlib.import_module(module_name)
    target = getattr(module, attr_name, None)
    run_callable = _resolve_run_callable(target, entrypoint)
    sdk_context = _build_context(extension, workload, context)
    result = run_callable(sdk_context, dict(request.get("input_payload", {})))
    if inspect.isawaitable(result):
        result = asyncio.run(result)
    if not isinstance(result, WorkloadResult):
        raise ValueError("E_SDK_WORKLOAD_RESULT_INVALID")
    return result


def _resolve_run_callable(target: Any, entrypoint: str) -> Any:
    if target is None:
        raise ValueError(f"E_SDK_ENTRYPOINT_MISSING: {entrypoint}")
    if inspect.isclass(target):
        instance = target()
        run_method = getattr(instance, "run", None)
        if run_method is None or not callable(run_method):
            raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {entrypoint}")
        return run_method
    if callable(target) and hasattr(target, "run"):
        run_method = getattr(target, "run", None)
        if run_method is None or not callable(run_method):
            raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {entrypoint}")
        return run_method
    if callable(target):
        return target
    raise ValueError(f"E_SDK_ENTRYPOINT_INVALID: {entrypoint}")


def _build_context(extension: dict[str, Any], workload: dict[str, Any], context: dict[str, Any]) -> WorkloadContext:
    workspace_root = Path(str(context["workspace_root"]))
    output_dir = Path(str(context["output_dir"]))
    input_config = dict(context.get("config", {}))
    capability_registry = WorkloadArtifacts.build_sdk_capability_registry(
        workspace=workspace_root,
        artifact_root=output_dir,
        input_config=input_config,
    )
    return WorkloadContext(
        extension_id=str(extension["extension_id"]),
        workload_id=str(workload["workload_id"]),
        run_id=str(context["run_id"]),
        workspace_root=workspace_root,
        input_dir=Path(str(context["input_dir"])),
        output_dir=output_dir,
        capabilities=capability_registry,
        seed=int(context.get("seed", 0) or 0),
        config=input_config,
    )


def _is_importlib_bootstrap_frame(path: Path) -> bool:
    return "importlib" in path.parts and path.name.startswith("_bootstrap")


def _guarded_import(import_hook: DeclaredStdlibImportHook, original_import: Any) -> Any:
    def _import(
        name: str,
        globals: dict[str, Any] | None = None,
        locals: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if level == 0:
            import_hook.validate_import(name)
        return original_import(name, globals, locals, fromlist, level)

    return _import


def _guarded_import_module(import_hook: DeclaredStdlibImportHook, original_import_module: Any) -> Any:
    def _import_module(name: str, package: str | None = None) -> Any:
        import_hook.validate_import(name)
        return original_import_module(name, package)

    return _import_module


if __name__ == "__main__":
    raise SystemExit(main())
