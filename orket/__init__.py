from .orket import orchestrate, orchestrate_rock, ConfigLoader
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("orket")
except PackageNotFoundError:
    # Package is not installed (e.g. during local development)
    __version__ = "0.3.9-local"

__all__ = [
    "orchestrate",
    "orchestrate_rock",
    "ConfigLoader",
    "__version__",
]
