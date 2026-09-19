"""Publish an exclusively staged bootstrap directory in an owned synchronous worker."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

side_effecting = True
logger = logging.getLogger(__name__)


def publish_run_start_directory(staging: Path, destination: Path, *, retry_seconds: float) -> None:
    """Retry only native Windows access/sharing refusals, without rebuilding evidence.

    The caller exclusively creates staging and retains this worker through cancellation.
    This is a cooperating-writer protocol, not protection against hostile filesystem mutation.
    """
    source_identity = staging.stat()
    deadline = time.monotonic() + retry_seconds
    attempts = 0
    while True:
        # lexists semantics also reject dangling symlinks. Staging's exclusive
        # creation already excludes another cooperating bootstrap publisher.
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"E_RUN_START_ARTIFACTS_PUBLISH_CONFLICT:{destination}")
        attempts += 1
        try:
            staging.rename(destination)
            break
        except PermissionError as exc:
            remaining = deadline - time.monotonic()
            if getattr(exc, "winerror", None) not in {5, 32}:
                raise
            if remaining <= 0:
                raise RuntimeError(
                    f"E_RUN_START_ARTIFACTS_PUBLISH_BLOCKED:{staging}:attempts={attempts}:{exc}"
                ) from exc
            if attempts == 1:
                logger.warning("E_RUN_START_ARTIFACTS_PUBLISH_RETRY:%s:winerror=%s", staging, exc.winerror)
            # Blocking wait is confined to the caller-owned storage worker.
            threading.Event().wait(min(0.05, remaining))
    published_identity = destination.stat()
    if staging.exists() or (source_identity.st_dev, source_identity.st_ino) != (
        published_identity.st_dev, published_identity.st_ino
    ):
        raise RuntimeError(f"E_RUN_START_ARTIFACTS_PUBLISH_UNVERIFIED:{destination}")
    if attempts > 1:
        logger.warning("RUN_START_ARTIFACTS_PUBLISHED_AFTER_RETRY:%s:attempts=%s", destination, attempts)
