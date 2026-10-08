"""Worker-owned dotenv updates; preserve unrelated content and verify selected values."""
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import dotenv_values, set_key

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes

side_effecting = True


def publish_project_environment(root: Path, values: dict[str, str]) -> str:
    require_sync_context(code="E_SETUP_ENVIRONMENT_REQUIRES_NATIVE_OWNER")
    root = root.resolve()
    path = root / ".env"
    with NativeFileLocks(path, suffix=".setup-locks", error_prefix="E_SETUP_ENVIRONMENT",
                         empty_key_error="E_SETUP_ENVIRONMENT_LOCK_KEY").hold_sync("environment"):
        require_regular_or_absent(path, error_code="E_SETUP_ENVIRONMENT_NOT_REGULAR")
        original = path.read_bytes() if path.exists() else b""
        # python-dotenv owns its quoting and editing semantics. The actual .env is
        # published only after every selected key survives a parse of the staged bytes.
        with TemporaryDirectory(prefix=".orket-env-", dir=root) as temporary:
            staged = Path(temporary) / ".env"
            staged.write_bytes(original)
            for key, value in values.items():
                set_key(staged, key, value, quote_mode="always", encoding="utf-8")
            content = staged.read_bytes()
        observed = dotenv_values(stream=StringIO(content.decode("utf-8")), interpolate=False)
        if any(observed.get(key) != value for key, value in values.items()):
            raise ValueError("E_SETUP_ENVIRONMENT_VALUES_UNVERIFIED")
        write_verified_bytes(path, content, error_code="E_SETUP_ENVIRONMENT_UNVERIFIED")
    return str(path)
