"""Application capture of immutable policy for one workload invocation."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from .models import RELIABLE_MODE_ENV, RELIABLE_REQUIRE_CLEAN_GIT_ENV


@dataclass(frozen=True)
class WorkloadPolicy:
    reliable_mode_enabled: bool
    reliable_require_clean_git: bool
    provenance_verbose_enabled: bool
    artifact_file_size_cap_bytes: int
    artifact_total_size_cap_bytes: int

    def identity_inputs(self) -> dict[str, bool | int]:
        return asdict(self)


def _size_cap(environment: dict[str, str], key: str, default: int) -> int:
    raw = environment.get(key, "").strip()
    return max(1, int(raw)) if raw else default


def capture_workload_policy() -> WorkloadPolicy:
    environment = dict(os.environ)
    enabled = {"1", "true", "yes", "on"}
    return WorkloadPolicy(
        reliable_mode_enabled=environment.get(RELIABLE_MODE_ENV, "true").strip().lower()
        not in {"0", "false", "no", "off"},
        reliable_require_clean_git=environment.get(RELIABLE_REQUIRE_CLEAN_GIT_ENV, "").strip().lower() in enabled,
        provenance_verbose_enabled=environment.get("ORKET_EXT_PROVENANCE_VERBOSE", "").strip().lower() in enabled,
        artifact_file_size_cap_bytes=_size_cap(environment, "ORKET_EXT_ARTIFACT_FILE_SIZE_CAP_BYTES", 32 * 1024 * 1024),
        artifact_total_size_cap_bytes=_size_cap(environment, "ORKET_EXT_ARTIFACT_TOTAL_SIZE_CAP_BYTES", 128 * 1024 * 1024),
    )
