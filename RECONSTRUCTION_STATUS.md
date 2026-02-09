# Reconstruction Status - DO NOT DELETE

**Session**: 2026-02-09
**Status**: IN PROGRESS - Context about to compact
**Phase**: Week 1, Day 1 - Building new execution engine

---

## What We're Doing

**RECONSTRUCTION** - Not rebuild. We're replacing the broken parts while keeping the good domain models.

**Why**: Two brutal code reviews (Claude + Gemini) found:
- RCE vulnerability in verification system
- 200-line god method (_traction_loop)
- Sync I/O blocking async event loop
- 15+ bare except clauses
- Path traversal vulnerability

**Decision**: Selective reconstruction over 2 weeks, not 4-week full refactor.

---

## Files Created This Session

### Phase 3.1 Webhook Integration (COMPLETE)
- `orket/webhook_server.py` - FastAPI server ✅
- `orket/services/webhook_db.py` - SQLite persistence ✅
- `orket/services/gitea_webhook_handler.py` - Updated with sandbox integration ✅
- `tests/test_sandbox_compose_generation.py` - Tests passing (3/3) ✅
- `docs/GITEA_WEBHOOK_SETUP.md` - Setup guide ✅

### Code Reviews (COMPLETE)
- `docs/CODE_REVIEW_2026-02-09.md` - My review (6.5/10 score) ✅
- `docs/BRUTAL_PATH.md` - Combined analysis + 4-week plan ✅

### Reconstruction (IN PROGRESS)
- `orket/orchestration/turn_executor.py` - **NEW** execution engine ✅
  - 300 lines, single responsibility
  - Async native (no blocking I/O)
  - Specific exceptions (no bare except)
  - Clean separation of concerns

- `orket/infrastructure/async_card_repository.py` - **NEW** async DB layer ✅
  - Uses aiosqlite (not blocking sqlite3)
  - All methods truly async
  - Includes adapter for gradual migration

---

## Next Steps (Resume Here)

### Immediate (Next Session)

1. **Create Async File Tools** (30 min)
   ```python
   # orket/infrastructure/async_file_tools.py
   # Use aiofiles instead of blocking Path.write_text()
   ```

2. **Fix Path Traversal Vulnerability** (30 min)
   ```python
   # orket/tools.py:_resolve_safe_path
   # Replace str.startswith with Path.is_relative_to()
   ```

3. **Wire TurnExecutor to Existing Code** (2 hours)
   - Update `orket/orket.py` to use TurnExecutor
   - Keep old _traction_loop commented for reference
   - Run tests to ensure no regressions

### This Week

**Day 2-3**: Fix RCE vulnerability
- Separate agent write dir from verification dir
- Sandbox verification in Docker (or at minimum, read-only fixtures)

**Day 4-5**: Complete async migration
- Replace all `requests` with `httpx`
- Use `aiofiles` for file I/O
- Fix all bare except clauses

---

## Critical Context

### Security Vulnerabilities (BLOCKING v1.0)

1. **RCE in VerificationEngine**
   - Location: `orket/domain/verification.py`
   - Attack: Agent writes malicious code → verification executes it
   - Fix: Separate directories OR sandbox in Docker

2. **Path Traversal on Windows**
   - Location: `orket/tools.py:22`
   - Issue: String comparison fails on case-insensitive paths
   - Fix: Use `Path.is_relative_to()` (Python 3.9+)

### Architecture Decisions

**Keep These** (domain models are solid):
- `orket/domain/state_machine.py`
- `orket/domain/critical_path.py`
- `orket/schema.py`
- All test files

**Replace These** (execution engine):
- `orket/orket.py:_traction_loop` → Use TurnExecutor
- `orket/infrastructure/sqlite_repositories.py` → Use AsyncCardRepository
- `orket/tools.py` → Fix path validation, add async file tools

**Fix These** (quality issues):
- All bare `except:` clauses → Specific exceptions
- All `datetime.utcnow()` → `datetime.now(UTC)`
- `requirements.txt` + `pyproject.toml` → Consolidate to pyproject.toml

---

## Test Results

**All tests passing before reconstruction**:
- `tests/test_golden_flow.py` - 2/2 ✅
- `tests/test_sandbox_compose_generation.py` - 3/3 ✅
- `tests/test_idesign_enforcement.py` - Passing ✅

**Goal**: Keep all tests passing during reconstruction.

---

## Dependencies to Add

```toml
# Add to pyproject.toml
dependencies = [
    "aiosqlite>=0.19.0,<0.20.0",  # Async SQLite
    "httpx>=0.26.0,<0.27.0",      # Async HTTP
    "aiofiles>=23.2.0,<24.0.0",   # Async file I/O
    # ... existing deps with version pins
]
```

---

## Windows Environment Notes

**CRITICAL**: Windows bash doesn't support `&&` for chaining commands.
- ❌ WRONG: `git push && git push --tags`
- ✅ CORRECT: Use separate commands or `;` separator

**Backup Location**: V:\OrketBackup (separate drive from source)

---

## User Preferences

1. **No emojis in documentation** (only in messages to user)
2. **FastAPI** (not Flask) for all HTTP
3. **Local-first** (no cloud dependencies)
4. **iDesign enforcement** at 7 issues per epic
5. **Mechanical governance** (State Machine, not "vibes")

---

## Git Status

**Branch**: main
**Last Commit**: 0b3e099 "docs(critical): Add BRUTAL_PATH.md"
**Uncommitted**:
- `orket/orchestration/turn_executor.py` (new)
- `orket/infrastructure/async_card_repository.py` (new)
- `RECONSTRUCTION_STATUS.md` (this file)

---

## Contacts & Resources

**GitHub**: https://github.com/McElyea/Orket
**Reviews**:
- Claude review: docs/CODE_REVIEW_2026-02-09.md
- Gemini review: Provided by user, harsh but accurate
**Plan**: docs/BRUTAL_PATH.md

---

## Key Quotes to Remember

**Gemini**: "Conceptually 8/10. Implementation 3/10."

**Claude**: "This is a promising project with concerning quality issues."

**User**: "Should we just rebuild from scratch?"

**Claude**: "No. Reconstruct selectively."

---

## Resume Instructions

When context resumes:
1. Read this file first
2. Check git status
3. Continue with "Next Steps" section
4. Run tests frequently
5. Commit after each working piece

**Current Priority**: Fix path traversal, then wire TurnExecutor.

---

**Last Updated**: 2026-02-09 (before context compaction)
**Status**: Ready to continue reconstruction
