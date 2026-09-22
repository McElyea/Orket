"""Immutable network inputs for one owned provider catalog client."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderHttpInputs:
    # Proxy URLs may contain credentials; never include them in diagnostic reprs.
    proxy_mounts: tuple[tuple[str, str | None], ...] = field(repr=False)
    certificate_file: Path | None = None
    certificate_directory: Path | None = None
    keylog_file: Path | None = None


class ProviderInferenceHttpPort(Protocol):
    def create_client(self, *, backend: str, base_url: str, timeout_s: float, connect_timeout_s: float) -> Any: ...

    async def close(self, client: Any = None) -> None: ...
