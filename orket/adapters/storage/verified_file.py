"""Owned synchronous file publication; callers supply local concurrency ownership."""
import os
import tempfile
from pathlib import Path

from orket.core.contracts.protocol_error_codes import E_FILE_WRITE_UNVERIFIED

side_effecting = True


def write_verified_bytes(path: Path, payload: bytes, *, error_code: str = E_FILE_WRITE_UNVERIFIED) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        if path.read_bytes() != payload:
            raise OSError(error_code)
    finally:
        temporary.unlink(missing_ok=True)
