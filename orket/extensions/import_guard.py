from __future__ import annotations

import importlib.abc
import sys
from dataclasses import dataclass, field
from types import TracebackType
from typing import Iterable

DEFAULT_BLOCKED_PREFIXES: tuple[str, ...] = ("orket",)
DEFAULT_ALLOWED_PREFIXES: tuple[str, ...] = ("orket_extension_sdk",)


def _matches_module_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(f"{prefix}.")


class ExtensionImportGuard(importlib.abc.MetaPathFinder):
    """Blocks internal `orket.*` imports while external workloads execute."""

    def __init__(
        self,
        *,
        blocked_prefixes: Iterable[str] = DEFAULT_BLOCKED_PREFIXES,
        allowed_prefixes: Iterable[str] = DEFAULT_ALLOWED_PREFIXES,
    ) -> None:
        self._blocked_prefixes = tuple(str(value).strip() for value in blocked_prefixes if str(value).strip())
        self._allowed_prefixes = tuple(str(value).strip() for value in allowed_prefixes if str(value).strip())

    def is_blocked(self, module_name: str) -> bool:
        fullname = str(module_name or "").strip()
        if not fullname:
            return False
        for prefix in self._allowed_prefixes:
            if _matches_module_prefix(fullname, prefix):
                return False
        for prefix in self._blocked_prefixes:
            if _matches_module_prefix(fullname, prefix):
                return True
        return False

    def find_spec(self, fullname: str, path: object = None, target: object = None) -> object | None:
        if self.is_blocked(fullname):
            raise ImportError(
                "E_EXT_IMPORT_BLOCKED: "
                f"'{fullname}' is internal host runtime surface; use orket_extension_sdk contracts."
            )
        return None


@dataclass(slots=True)
class ImportGuardContext:
    """Installs `ExtensionImportGuard` for a narrow workload execution window."""

    guard: ExtensionImportGuard = field(default_factory=ExtensionImportGuard)
    _installed: bool = field(default=False, init=False, repr=False)

    def __enter__(self) -> ImportGuardContext:
        if self.guard in sys.meta_path:
            return self
        sys.meta_path.insert(0, self.guard)
        self._installed = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._installed:
            return
        try:
            sys.meta_path.remove(self.guard)
        except ValueError:
            pass
        finally:
            self._installed = False
