from .orket import orchestrate, orchestrate_rock, ConfigLoader
from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
import tomllib


def _read_pyproject_version() -> str | None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject_path.exists():
        return None
    try:
        with pyproject_path.open("rb") as handle:
            payload = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = str((payload.get("project") or {}).get("version") or "").strip()
    return value or None


def _resolve_runtime_version() -> str:
    try:
        return version("orket")
    except PackageNotFoundError:
        pyproject_version = _read_pyproject_version()
        if pyproject_version:
            return f"{pyproject_version}-local"
        return "0.0.0-local"


__version__ = _resolve_runtime_version()

__all__ = [
    "orchestrate",
    "orchestrate_rock",
    "ConfigLoader",
    "__version__",
]
