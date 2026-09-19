"""Select and verify extension module origins in an owned synchronous worker.

This is trusted-code admission, not an OS containment boundary. Python retains
same-origin modules for the process lifetime; selecting another root must refuse
instead of adopting that cached object. Imports can have non-transactional effects.
"""
from __future__ import annotations

import importlib
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

# sys.path and the module cache are process-wide, across every loader instance.
_LOAD_LOCK = threading.RLock()
side_effecting = True


@dataclass(frozen=True)
class ExtensionModuleSource:
    name: str
    origin: Path | None
    package_path: Path | None


def extension_module_sources(root: Path, module_name: str) -> tuple[ExtensionModuleSource, ...]:
    """Resolve Python's package precedence and every parent without executing it."""
    parts = module_name.split('.')
    if not parts or any(not part.isidentifier() for part in parts):
        raise ValueError(f"E_EXT_MODULE_NAME_INVALID: {module_name}")
    if parts[0] in {'orket', 'orket_extension_sdk'}:
        raise ValueError(f"E_EXT_MODULE_NAME_RESERVED: {module_name}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    selected = []
    for index in range(len(parts)):
        name = '.'.join(parts[:index + 1])
        module_path = root.joinpath(*parts[:index + 1])
        package_init = module_path / '__init__.py'
        source_file = module_path.with_suffix('.py')
        if package_init.is_file():
            origin, package = package_init.resolve(strict=True), module_path.resolve(strict=True)
        elif source_file.is_file() and index == len(parts) - 1:
            origin, package = source_file.resolve(strict=True), None
        elif module_path.is_dir() and not source_file.is_file() and index < len(parts) - 1:
            origin, package = None, module_path.resolve(strict=True)
        else:
            raise FileNotFoundError(f"Extension module source not found for '{name}' under {root}")
        if any(path is not None and not path.is_relative_to(root) for path in (origin, package)):
            raise ValueError(f"E_EXT_MODULE_SOURCE_OUTSIDE_ROOT: {name}")
        selected.append(ExtensionModuleSource(name, origin, package))
    return tuple(selected)


def read_extension_sources(root: Path, module_name: str) -> tuple[tuple[Path, str], ...]:
    return tuple((source.origin, source.origin.read_text(encoding='utf-8'))
                 for source in extension_module_sources(root, module_name) if source.origin is not None)


def _verify_origin(module: ModuleType, source: ExtensionModuleSource) -> None:
    spec = getattr(module, '__spec__', None)
    origin = getattr(spec, 'origin', None)
    observed_file = getattr(module, '__file__', None)
    paths = tuple(Path(value).resolve() for value in getattr(module, '__path__', ()))
    expected_paths = () if source.package_path is None else (source.package_path,)
    matches = getattr(spec, 'name', None) == source.name and paths == expected_paths
    if source.origin is None:
        matches = matches and origin is None and observed_file is None
    else:
        matches = (matches and isinstance(origin, str) and Path(origin).resolve() == source.origin
                   and isinstance(observed_file, str) and Path(observed_file).resolve() == source.origin)
    if not matches:
        raise ImportError(
            f"E_EXT_MODULE_ORIGIN_MISMATCH: {source.name}; selected {source.origin or source.package_path}, "
            f"observed {origin!r}. Use a fresh process or distinct module names for different extension roots."
        )


@contextmanager
def extension_module_scope(root: Path, module_name: str) -> Iterator[ModuleType]:
    """Retain selected path admission through import and immediate construction."""
    with _LOAD_LOCK:
        root = root.resolve(strict=True)
        sources = extension_module_sources(root, module_name)
        for source in sources:
            cached = sys.modules.get(source.name)
            if cached is not None:
                _verify_origin(cached, source)
        inserted = str(root)
        sys.path.insert(0, inserted)
        try:
            for source in sources:
                module = importlib.import_module(source.name)
                _verify_origin(module, source)
            yield module
        finally:
            # Remove our exact insertion without deleting a pre-existing equal path.
            for index, entry in enumerate(sys.path):
                if entry is inserted:
                    del sys.path[index]
                    break


def load_extension_module(root: Path, module_name: str) -> ModuleType:
    """Verify cached parents before imports, then verify actual origins before adoption."""
    with extension_module_scope(root, module_name) as module:
        return module
