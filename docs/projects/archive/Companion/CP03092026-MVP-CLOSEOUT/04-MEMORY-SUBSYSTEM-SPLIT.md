# Implementation Plan: Memory Subsystem Split (session_memory + profile_memory)

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1 (SDK/host seam hardening)
**Depends on**: 03-CAPABILITY-WIRING (models), 02-SDK-PACKAGE-HARDENING
**Estimated Scope**: ~8 files touched, ~500 lines added/changed

## Problem

Companion requires two distinct memory scopes: `session_memory` (chronological, bounded, per-session) and `profile_memory` (persistent key/value + fact records, cross-session). The current `MemoryStore` is a single `project_memory` table with no scope concept, no session isolation, no key/value profile records, and no write policy enforcement.

## Current State

**MemoryStore** (`orket/services/memory_store.py`):
- Single `project_memory` table in aiosqlite
- `remember(content, metadata)` -- insert with keyword extraction
- `search(query, limit)` -- keyword matching with scoring
- No session_id column, no scope column, no key column
- No write policy (anything can write anything)

**MemoryCommitBuffer** (`orket/application/services/memory_commit_buffer.py`):
- MVCC-style buffer for memory writes: open -> pending -> applied/aborted
- `InMemoryCommitStore` and `JsonFileCommitStore` backends
- No scope awareness

**MemoryAccessPolicy** (`orket/application/services/memory_access_policy.py`):
- Role-based access control (utility agent profiles)
- `normalize_retrieval_rows()` limits results per profile
- No session/profile scope concept

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No session_memory scope | BLOCKING | Companion needs per-session chronological memory |
| No profile_memory scope | BLOCKING | Companion needs persistent cross-session key/value memory |
| No session_id on memory records | BLOCKING | Cannot isolate session memory |
| No key column for profile records | HIGH | Profile memory needs deterministic key-based lookup |
| No write policy enforcement | HIGH | Profile writes must be restricted to approved categories |
| No memory toggle controls | HIGH | Session and profile memory need enable/disable toggles |
| No clear-session-memory operation | MEDIUM | Plan requires clearing session without touching profile |
| No deterministic retrieval order for profile | MEDIUM | Tie-break rules needed for profile queries |
| Commit buffer not scope-aware | LOW | Works but doesn't validate scope on commit |

## Implementation Steps

### Step 1: Schema migration -- add scope, session_id, key columns

New table schema (or migrate existing `project_memory`):
```sql
CREATE TABLE memory_records (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('session', 'profile')),
    session_id TEXT,          -- required for scope='session', NULL for profile
    key TEXT,                 -- required for scope='profile', NULL for session
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    keywords TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_memory_scope ON memory_records(scope);
CREATE INDEX idx_memory_session ON memory_records(session_id) WHERE scope = 'session';
CREATE INDEX idx_memory_profile_key ON memory_records(key) WHERE scope = 'profile';
```

### Step 2: Implement ScopedMemoryStore

New class wrapping or replacing `MemoryStore`. Separate profile-memory access patterns explicitly:

```python
class ScopedMemoryStore:
    # --- Session memory: chronological, append-only, bounded ---
    async def write_session(self, session_id: str, content: str, metadata: dict) -> str
    async def query_session(self, session_id: str, query: str | None, limit: int) -> list[MemoryRecord]
    async def clear_session(self, session_id: str) -> int  # returns count deleted

    # --- Profile memory: three distinct access patterns ---
    # 1. Exact key lookup (for settings, known facts)
    async def read_profile(self, key: str) -> MemoryRecord | None
    # 2. Upsert by key (for settings/state; fact records may use different semantics)
    async def write_profile(self, key: str, content: str, metadata: dict) -> str
    # 3. Deterministic browsable listing (alphabetical key order)
    async def list_profile(self, limit: int | None = None) -> list[MemoryRecord]
    # 4. Optional lexical query (keyword search within profile records)
    async def query_profile(self, query: str, limit: int) -> list[MemoryRecord]
    # Individual key deletion only -- no bulk profile clear
    async def delete_profile(self, key: str) -> bool
```

**Record type distinction**: Profile memory stores both canonical key/value settings (e.g., `companion_setting.role_id`) and user fact records (e.g., `user_fact.name`). Settings use upsert-by-key. Fact records use the same key model but require `user_confirmed` metadata for writes. This distinction is enforced by the write policy, not by separate storage.

**Retrieval order rules** (documented per access pattern):
- Session `query_session`: chronological by `created_at` DESC (most recent first), bounded by `limit` (count-based)
- Profile `read_profile`: exact key match, single result
- Profile `list_profile`: alphabetical by `key` ASC, then `created_at` ASC for ties
- Profile `query_profile`: keyword relevance score DESC, then `key` ASC for ties

### Step 3: Write policy enforcement

Companion plan restricts profile writes to:
1. Explicit user-approved preferences
2. Stable user facts (confirmation-gated)
3. Persisted Companion settings/mode state

```python
ALLOWED_PROFILE_KEY_PREFIXES = [
    "user_preference.",    # e.g., user_preference.theme
    "user_fact.",          # e.g., user_fact.name (requires confirmation flag)
    "companion_setting.",  # e.g., companion_setting.role_id
    "companion_mode.",     # e.g., companion_mode.relationship_style
]

class ProfileWritePolicy:
    def validate(self, key: str, metadata: dict) -> bool:
        # Check key prefix allowlist
        # For user_fact.*, require metadata["user_confirmed"] == True
```

### Step 4: Memory toggle controls

```python
@dataclass
class MemoryControls:
    profile_memory_enabled: bool = True    # profile-level default
    session_memory_enabled: bool = True    # session-level override (resets on new session)

    def effective_session_enabled(self) -> bool:
        return self.session_memory_enabled

    def effective_profile_enabled(self) -> bool:
        return self.profile_memory_enabled
```

Profile-level memory controls are persisted in profile memory under reserved Companion setting keys (e.g., `companion_setting.memory_profile_enabled`), with bootstrap-safe defaults that do not require prior profile-memory reads to determine whether profile-memory reads are allowed. Default is `True` (enabled); the toggle only needs to be read if it was previously written.

Session toggle is in-memory, resets on new session.

Guard: `ScopedMemoryStore` checks toggles before write/query.

### Step 5: Session retrieval hook

Per the plan: "Session retrieval runs before every generation turn when memory is enabled."

This is host-owned behavior. The host API chat endpoint runs retrieval before calling model.generate:
```python
async def pre_turn_memory_retrieval(session_id: str, store: ScopedMemoryStore, controls: MemoryControls) -> list[MemoryRecord]:
    records = []
    if controls.effective_session_enabled():
        records.extend(await store.query_session(session_id, query=None, limit=RECENT_WINDOW_SIZE))
    if controls.effective_profile_enabled():
        records.extend(await store.list_profile(limit=PROFILE_WINDOW_SIZE))
    return records
```

### Step 6: Wire to capability registry

Connect `ScopedMemoryStore` to `HostMemoryProvider` (from Plan 03):
- `memory.write` routes to `write_session()` or `write_profile()` based on scope
- `memory.query` routes to `query_session()`, `read_profile()`, `list_profile()`, or `query_profile()` based on scope and parameters
- Write policy enforced on `memory.write` for profile scope

### Step 7: Migration path for existing data

Existing `project_memory` rows are migrated into a legacy compatibility scope or tagged legacy session namespace. They are not silently treated as equivalent to real Companion session memory semantics.

- Existing rows get `scope='legacy'`, `session_id='legacy_migration'`, `key=NULL`
- One-time migration script, idempotent
- Legacy scope is queryable but does not appear in standard Companion session/profile queries

## Acceptance Criteria

1. `write_session()` creates records scoped to session_id; `query_session()` returns only that session's records
2. `write_profile()` upserts by key; `read_profile()` returns exact key match
3. `clear_session(session_id)` deletes only that session's records, profile untouched
4. Profile write policy rejects keys outside the allowlist
5. Memory toggles disable read/write when off; session toggle resets on new session
6. Session retrieval returns chronological recent window (bounded by count)
7. Profile listing returns deterministic order (alphabetical key, then created_at for ties)
8. Existing `project_memory` data migrated to legacy scope without loss
9. Session/profile semantics remain stable even after future episodic-memory introduction; episodic retrieval must not alter the behavior of MVP session/profile reads

## Files to Create/Modify

| Action | Path |
|--------|------|
| CREATE | `orket/services/scoped_memory_store.py` |
| CREATE | `orket/services/profile_write_policy.py` |
| MODIFY | `orket/services/memory_store.py` (deprecation marker or thin wrapper) |
| MODIFY | `orket/capabilities/host_memory_provider.py` (wire to scoped store) |
| CREATE | `tests/application/test_scoped_memory_store.py` |
| CREATE | `tests/application/test_profile_write_policy.py` |
| CREATE | `tests/application/test_memory_toggle_controls.py` |
