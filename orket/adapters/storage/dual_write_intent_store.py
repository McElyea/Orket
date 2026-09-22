"""Verified, bound intent storage for cooperating local dual-ledger owners."""
import json
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.protocol_ledger_io import owned_protocol_io
from orket.adapters.storage.verified_file import write_verified_bytes
from orket.core.contracts.dual_write_intent import DualWriteLedgerError, validate_intent
from orket.core.contracts.local_file_lock import LocalFileLockError
from orket.core.contracts.protocol_error_codes import E_DUAL_WRITE_PREFIX, format_protocol_error

side_effecting = True


class DualWriteIntentStore:
    side_effecting = True

    def __init__(self, *, sqlite_path: str | Path, protocol_root: str | Path):
        self.sqlite_path, self.protocol_root = Path(sqlite_path), Path(protocol_root)
        if not self.sqlite_path.is_absolute() or not self.protocol_root.is_absolute():
            raise DualWriteLedgerError("BINDING_REQUIRED:absolute_backend_paths")
        self.path = self.sqlite_path.with_name(self.sqlite_path.name + ".dual-write-intents.json")
        self._binding = None

    def _bind(self):
        if self._binding is None:
            self.sqlite_path, self.protocol_root = self.sqlite_path.resolve(), self.protocol_root.resolve()
            self.path = self.sqlite_path.with_name(self.sqlite_path.name + ".dual-write-intents.json")
            self._binding = {"sqlite": str(self.sqlite_path), "protocol": str(self.protocol_root)}

    @asynccontextmanager
    async def hold(self):
        await owned_protocol_io(self._bind)
        locks = [NativeFileLocks(root, suffix=suffix, error_prefix="E_DUAL_WRITE",
                                 empty_key_error="E_DUAL_WRITE_OWNER_REQUIRED")
                 for root, suffix in ((self.path, ".owners"), (self.protocol_root, ".dual-ledger-owners"))]
        try:
            async with AsyncExitStack() as owners:
                for lock in sorted(locks, key=lambda item: str(item.root_path) + item.suffix):
                    await owners.enter_async_context(lock.hold("lifecycle"))
                yield
        except LocalFileLockError as exc:
            raise LocalFileLockError(format_protocol_error(E_DUAL_WRITE_PREFIX, str(exc))) from exc

    def _legacy_check(self):
        legacy = self.sqlite_path.parent / ".orket" / "dual_write_intents.json"
        try:
            payload = json.loads(legacy.read_bytes())
        except FileNotFoundError:
            return
        except ValueError as exc:
            raise DualWriteLedgerError(f"LEGACY_UNBOUND:{legacy}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != "1.0" or payload.get("pending") != []:
            raise DualWriteLedgerError(f"LEGACY_UNBOUND:{legacy}")

    async def load(self):
        return await owned_protocol_io(self._load)

    def _load(self):
        self._legacy_check()
        try:
            payload = json.loads(self.path.read_bytes())
        except FileNotFoundError:
            return []
        except ValueError as exc:
            raise DualWriteLedgerError("INTENT_SCHEMA:json") from exc
        if (not isinstance(payload, dict) or payload.get("schema_version") != "2.0"
                or payload.get("binding") != self._binding or not isinstance(payload.get("pending"), list)):
            raise DualWriteLedgerError("INTENT_SCHEMA:binding_or_version")
        rows = payload["pending"]
        identities = set()
        for row in rows:
            validate_intent(row)
            if row["intent_id"] in identities:
                raise DualWriteLedgerError("INTENT_SCHEMA:duplicate")
            identities.add(row["intent_id"])
        return rows

    async def write(self, intents):
        for row in intents:
            validate_intent(row)
        payload = json.dumps({"schema_version": "2.0", "binding": self._binding, "pending": intents},
                             ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
        await owned_protocol_io(write_verified_bytes, self.path, payload,
                                error_code=format_protocol_error(E_DUAL_WRITE_PREFIX, "WRITE_UNVERIFIED"))
