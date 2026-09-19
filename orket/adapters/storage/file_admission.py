"""Filesystem admission checks run inside an owned storage worker."""
import stat
from pathlib import Path

side_effecting = False


def require_regular_or_absent(path: Path, *, error_code: str) -> None:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return
    if (not stat.S_ISREG(observed.st_mode)
            or getattr(observed, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise ValueError(error_code)
