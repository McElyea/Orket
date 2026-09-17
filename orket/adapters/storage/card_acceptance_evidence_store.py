"""Content-addressed retained acceptance evidence; this store cannot complete cards."""
from __future__ import annotations

import hashlib
from pathlib import Path

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal

MAX_EVIDENCE_BYTES = 33_554_432


class CardAcceptanceEvidenceStore:
    side_effecting = True

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    async def put(self, payload: str) -> str:
        encoded = payload.encode("utf-8")
        if len(encoded) > MAX_EVIDENCE_BYTES:
            raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_LIMIT")
        digest = hashlib.sha256(encoded).hexdigest()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            await conn.execute("CREATE TABLE IF NOT EXISTS card_acceptance_evidence (digest TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            for operation in ("UPDATE", "DELETE"):
                await conn.execute(
                    f"CREATE TRIGGER IF NOT EXISTS card_acceptance_evidence_no_{operation.lower()} "
                    f"BEFORE {operation} ON card_acceptance_evidence BEGIN "
                    "SELECT RAISE(ABORT, 'E_CARD_ACCEPTANCE_EVIDENCE_IMMUTABLE'); END"
                )
            await conn.execute("INSERT OR IGNORE INTO card_acceptance_evidence VALUES (?, ?)", (digest, payload))
            cursor = await conn.execute("SELECT payload FROM card_acceptance_evidence WHERE digest = ?", (digest,))
            row = await cursor.fetchone()
            if row is None or row[0] != payload:
                raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_COLLISION")
            await conn.commit()
        return digest

    async def read(self, digest: str) -> str | None:
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_REFERENCE")
        uri = self.db_path.absolute().as_uri() + "?mode=ro"
        async with aiosqlite.connect(uri, uri=True) as conn:
            await conn.execute("PRAGMA query_only=ON")
            cursor = await conn.execute(
                "SELECT length(CAST(payload AS BLOB)), CASE WHEN length(CAST(payload AS BLOB)) <= ? THEN payload END "
                "FROM card_acceptance_evidence WHERE digest = ?",
                (MAX_EVIDENCE_BYTES, digest),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        if int(row[0]) > MAX_EVIDENCE_BYTES:
            raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_LIMIT")
        payload = str(row[1])
        if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
            raise ValueError("E_CARD_ACCEPTANCE_EVIDENCE_DIGEST")
        return payload
