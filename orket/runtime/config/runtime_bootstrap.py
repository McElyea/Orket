from __future__ import annotations

from pathlib import Path


class RuntimeBootstrapService:
    """Owns environment bootstrap and config-root fallback for runtime hosts."""

    def bootstrap_environment(self) -> None:
        from orket.settings import load_env

        load_env()

    def resolve_config_root(self, config_root: Path | None) -> Path:
        return config_root or Path().resolve()


DEFAULT_RUNTIME_BOOTSTRAP_SERVICE = RuntimeBootstrapService()
