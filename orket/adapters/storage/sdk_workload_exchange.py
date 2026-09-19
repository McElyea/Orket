"""Private SDK exchange storage; application retains every admitted worker."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

side_effecting = True


class SdkWorkloadExchange:
    side_effecting = True

    def __init__(self) -> None:
        self.root: Path | None = None
        self.cwd: Path | None = None
        self._parent: Path | None = None
        self._identity: tuple[int, int] | None = None

    def prepare(self, request_bytes: bytes) -> None:
        self.cwd = Path.cwd()
        # Store the handle before writing: cancellation must not lose this resource.
        self._parent = Path(tempfile.gettempdir()).resolve()
        self.root = Path(tempfile.mkdtemp(prefix="orket-sdk-workload-", dir=self._parent))
        observed = self.root.stat()
        self._identity = (observed.st_dev, observed.st_ino)
        (self.root / "request.json").write_bytes(request_bytes)

    def read_result(self) -> bytes:
        if self.root is None:
            raise RuntimeError("E_SDK_EXCHANGE_NOT_PREPARED")
        return (self.root / "result.json").read_bytes()

    def remove(self) -> None:
        if self.root is None:
            return
        # Only remove this worker's exact temporary directory, never a replacement.
        root = self.root
        if root.is_symlink() or root.resolve() != root or self._parent is None or not root.is_relative_to(self._parent):
            raise RuntimeError("E_SDK_EXCHANGE_IDENTITY_CHANGED")
        observed = root.stat()
        if (observed.st_dev, observed.st_ino) != self._identity:
            raise RuntimeError("E_SDK_EXCHANGE_IDENTITY_CHANGED")
        shutil.rmtree(root)
        if root.exists() or root.is_symlink():
            raise RuntimeError("E_SDK_EXCHANGE_REMOVAL_UNVERIFIED")
