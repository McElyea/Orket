"""Application authority for explicit extension scaffold commands."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.storage.async_executor_service import run_coroutine_blocking
from orket.adapters.storage.extension_template_store import (
    ExtensionTargetExists,
    ExtensionTemplateMissing,
    ExtensionTemplateStore,
)
from orket.core.contracts.extension_templates import EXTENSION_TEMPLATE_SOURCES


def extension_template_kinds() -> tuple[str, ...]:
    return tuple(sorted(kind for kind, _name in EXTENSION_TEMPLATE_SOURCES))


def init_external_extension(target: Path, *, force: bool = False, template_kind: str = "default") -> dict[str, Any]:
    """Synchronous CLI entrypoint; refuses event-loop callers before performing I/O."""
    return run_coroutine_blocking(create_external_extension(target, force=force, template_kind=template_kind))


async def create_external_extension(target: Path, *, force: bool = False, template_kind: str = "default") -> dict[str, Any]:
    template_name = dict(EXTENSION_TEMPLATE_SOURCES).get(template_kind)
    if template_name is None:
        raise ValueError(f"E_EXT_TEMPLATE_KIND_UNSUPPORTED: {template_kind}")
    try:
        observed = await ExtensionTemplateStore().materialize(template_name, target, force=force)
    except (ExtensionTemplateMissing, ExtensionTargetExists) as exc:
        missing = isinstance(exc, ExtensionTemplateMissing)
        return {"ok": False, "operation": "ext.init", "target": str(target), "error_count": 1,
                "errors": [{"code": "E_EXT_TEMPLATE_MISSING" if missing else "E_EXT_TARGET_EXISTS",
                            "location": "template" if missing else "target", "message": str(exc)}], "exit_code": 2}
    return {"ok": True, "operation": "ext.init", "target": str(target), "template": observed.template,
            "template_kind": template_kind, "copied_file_count": observed.copied_file_count,
            "error_count": 0, "errors": [], "exit_code": 0}
