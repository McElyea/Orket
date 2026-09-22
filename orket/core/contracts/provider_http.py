"""Immutable network inputs for one owned provider catalog client."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProviderHttpInputs:
    # Proxy URLs may contain credentials; never include them in diagnostic reprs.
    proxy_mounts: tuple[tuple[str, str | None], ...] = field(repr=False)
    certificate_file: Path | None = None
    certificate_directory: Path | None = None
    keylog_file: Path | None = None
