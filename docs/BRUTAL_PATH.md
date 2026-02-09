# The Brutal Path: Stop the Bleeding

**Date**: 2026-02-09
**Status**: 🔴 EMERGENCY - Technical Debt Crisis
**Verdict**: "Conceptually 8/10. Implementation 3/10" - Gemini

---

## The Hard Truth

We've built a beautiful wrapper around a fragile, insecure execution engine. The gap between our architectural vision (iDesign, SRP, Prompt Engine) and actual implementation is **embarrassing**.

**Two reviews. Same conclusion: Stop new features. Fix the foundation NOW.**

---

## 🔥 STOP EVERYTHING: Week 1 Critical Path

### Priority 0: Security Holes (DAY 1)

#### 1. Remote Code Execution Vulnerability
**Severity**: 🔴 **CRITICAL - EXPLOITABLE**
**Location**: `orket/domain/verification.py`

**The Problem**:
```python
# Agents can write malicious code to workspace
agent.write_file("verification/evil.py", "import os; os.system('rm -rf /')")

# Then trigger execution via verification
verify_issue(issue_id)  # ← Executes evil.py with full system access
```

**Gemini's Assessment**: "Remote Code Execution as a Service"

**Fix TODAY**:
```python
# Option 1: Separate directories (immediate)
AGENT_WRITE_DIR = workspace / "agent_output"
VERIFICATION_DIR = workspace / "verification" / ".readonly"  # Agent cannot write here

# Option 2: Sandbox verification (proper)
# Run verification in Docker container with no network, read-only filesystem
```

**Action**: Create GitHub issue "SECURITY: RCE via verification engine" - BLOCK v1.0 release.

---

#### 2. Path Traversal Bypass (Windows)
**Severity**: 🔴 **CRITICAL**
**Location**: `orket/tools.py:16-31`

**The Problem**:
```python
# Current code
in_workspace = str(resolved).startswith(str(self.workspace_root.resolve()))

# Windows bypass examples:
# - Case insensitivity: "C:\workspace" vs "c:\WORKSPACE"
# - Symlinks
# - UNC paths
```

**Gemini's Assessment**: "Notoriously fragile on Windows"

**Fix TODAY**:
```python
def _resolve_safe_path(self, path_str: str, write: bool = False) -> Path:
    """Secure path validation using Python 3.9+ is_relative_to()."""
    p = Path(path_str)
    if not p.is_absolute():
        p = self.workspace_root / p

    resolved = p.resolve(strict=False)

    # Use is_relative_to (Python 3.9+) instead of string comparison
    try:
        resolved.relative_to(self.workspace_root.resolve())
    except ValueError:
        # Also check references
        if not any(resolved.is_relative_to(r.resolve()) for r in self.references):
            raise PermissionError(f"Access denied: {path_str}")

    if write and not resolved.is_relative_to(self.workspace_root.resolve()):
        raise PermissionError(f"Write access restricted: {path_str}")

    return resolved
```

**Action**: Fix + security test suite for path traversal attempts.

---

### Priority 1: The God Method (DAY 2-3)

#### 3. Refactor `_traction_loop` (200-line monolith)
**Severity**: 🔴 **CRITICAL**
**Location**: `orket/orket.py:230-433`

**Gemini's Assessment**: "Definition of a God Method"

**Current Reality**:
```python
async def _traction_loop(...):  # 203 lines
    # Does EVERYTHING:
    # - Configuration loading
    # - Model selection
    # - Prompt compilation
    # - Agent execution
    # - State machine validation
    # - Error reporting
    # - Governance retries
    # - Transcript management
```

**Target Architecture** (by end of Week 1):
```python
# Broken into specialized services
class TurnOrchestrator:
    """Coordinates a single execution turn."""
    def __init__(self, turn_manager, governance_auditor, state_machine):
        self.turn_manager = turn_manager
        self.governance = governance_auditor
        self.state = state_machine

    async def execute_turn(self, issue: IssueConfig) -> TurnResult:
        # Single Responsibility: Coordinate one turn
        pass

class TurnManager:
    """Manages agent selection and prompt generation."""
    def prepare_turn(self, issue, role) -> PreparedTurn:
        pass

class GovernanceAuditor:
    """Validates tool calls and state transitions."""
    def audit_turn(self, turn: ExecutionTurn) -> AuditResult:
        pass

# Main loop becomes simple
async def _traction_loop(self, ...):
    orchestrator = TurnOrchestrator(...)

    while True:
        issue = self._get_next_issue()
        if not issue: break

        result = await orchestrator.execute_turn(issue)
        await self._persist_result(result)
```

**Action**: Create `orket/orchestration/turn_orchestrator.py` - Break up the monolith.

---

### Priority 2: Async/Await Disaster (DAY 4-5)

#### 4. Sync I/O in Async Context
**Severity**: 🔴 **CRITICAL**
**Files**: Multiple

**Gemini's Assessment**: "Entire engine will block during disk writes or slow DB queries"

**The Problem**:
```python
# BLOCKING in async function
async def _traction_loop(...):
    self.cards.save(card_data)  # ← BLOCKS event loop (sqlite3)
    path.write_text(content)     # ← BLOCKS event loop (file I/O)
    requests.post(url, ...)      # ← BLOCKS event loop (HTTP)
```

**Impact**: Webhook server freezes. Concurrent operations impossible.

**Fix Plan**:
1. **Replace sqlite3 with aiosqlite** (2 hours)
   ```python
   # Before
   import sqlite3
   conn = sqlite3.connect(db_path)

   # After
   import aiosqlite
   async with aiosqlite.connect(db_path) as conn:
       await conn.execute(...)
   ```

2. **Replace requests with httpx** (1 hour)
   ```python
   # Before
   import requests
   response = requests.post(url, ...)

   # After
   import httpx
   async with httpx.AsyncClient() as client:
       response = await client.post(url, ...)
   ```

3. **Use aiofiles for file I/O** (1 hour)
   ```python
   # Before
   path.write_text(content)

   # After
   import aiofiles
   async with aiofiles.open(path, 'w') as f:
       await f.write(content)
   ```

**Action**: Week 1 deliverable - All async functions must be truly async.

---

## 🟠 STOP THE CREEP: Week 2 Consolidation

### Priority 3: Exception Handling Crisis (15+ violations)

**Both Reviews Agree**: This is unacceptable.

**Mass Find/Replace Required**:
```bash
# Find all violations
grep -rn "except:\s*$" orket/
grep -rn "except:\s*pass" orket/

# 15 files affected
```

**Standard Pattern** (enforce via linter):
```python
# WRONG - NEVER DO THIS
try:
    operation()
except:
    pass

# CORRECT - Specific exceptions with context
try:
    operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise OperationFailedError(f"Context: {details}") from e
```

**Action**: Create `.ruff.toml` to enforce:
```toml
[lint]
select = ["E722"]  # Bare except
```

---

### Priority 4: datetime.utcnow() Removal

**Impact**: Breaks Python 3.12+

**Action**: Global search/replace (30 minutes)
```python
# Before
from datetime import datetime
timestamp = datetime.utcnow().isoformat() + "Z"

# After
from datetime import datetime, UTC
timestamp = datetime.now(UTC).isoformat()
```

---

### Priority 5: Dependency Management

**Both Reviews Agree**: Current state is chaos.

**Action**:
1. Delete `requirements.txt`
2. Consolidate to `pyproject.toml` with pins:
   ```toml
   dependencies = [
       "fastapi>=0.109.0,<0.110.0",
       "pydantic>=2.5.0,<3.0.0",
       "aiosqlite>=0.19.0,<0.20.0",
       "httpx>=0.26.0,<0.27.0",
       "aiofiles>=23.2.0,<24.0.0",
       # ... all with version constraints
   ]
   ```
3. Generate lock file: `pip-compile pyproject.toml`

---

## 🟡 BUILD IT RIGHT: Week 3-4 Foundation

### Priority 6: API Input Validation

**Gemini's Point**: "You've defined Pydantic schemas but don't use them for validation"

**Current State**:
```python
@app.post("/api/run")
async def run_active_asset(data: Dict[str, Any] = Body(...)):
    # ← No validation!
    asset_type = data.get("type")  # Could be anything
```

**Fix**:
```python
from pydantic import BaseModel, Field

class RunAssetRequest(BaseModel):
    type: Literal["epic", "rock", "issue"]
    name: str = Field(min_length=1, max_length=100)
    department: str = "core"

@app.post("/api/run")
async def run_active_asset(request: RunAssetRequest):
    # ← Automatic validation
    asset_type = request.type  # Guaranteed valid
```

---

### Priority 7: Database Layer

**Gemini's Point**: "Manual SQL strings are brittle"

**Options**:
1. **Short-term**: Keep SQLite, but use query builder
2. **Long-term**: Use SQLAlchemy with async support

**Action**: Evaluate SQLAlchemy vs maintaining manual queries.

---

### Priority 8: Hardcoded Configuration

**Files**: `server.py`, `orket/interfaces/api.py`

**Fix**: Environment-based config:
```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8082
    gitea_url: str = "http://localhost:3000"

    class Config:
        env_prefix = "ORKET_"
        env_file = ".env"

settings = Settings()
```

---

## 📊 The Brutal Metrics

### Current State
```
Security:           2/10  (RCE vulnerability, path traversal)
Architecture:       3/10  (God methods, tight coupling)
Async Correctness:  2/10  (Blocking everywhere)
Error Handling:     1/10  (Bare except clauses)
Type Safety:        6/10  (Partial hints)
Dependency Mgmt:    2/10  (No pins, conflicts)
API Design:         4/10  (No validation)
Testing:            7/10  (Good coverage, wrong things)
Documentation:      8/10  (Great vision, poor reality)
```

**Overall**: 3.5/10

### Target State (4 weeks)
```
Security:           9/10  (Sandboxed verification, secure paths)
Architecture:       8/10  (SRP enforced, services separated)
Async Correctness:  9/10  (Truly async throughout)
Error Handling:     9/10  (Specific exceptions, context)
Type Safety:        9/10  (Full mypy strict)
Dependency Mgmt:    9/10  (Pinned, locked)
API Design:         9/10  (Pydantic validation)
Testing:            9/10  (Security + concurrency tests)
Documentation:      9/10  (Matches reality)
```

**Target**: 8.5/10

---

## 🎯 4-Week Sprint Plan

### Week 1: STOP THE BLEEDING
**Goal**: Fix security holes, break up god method, make async truly async

**Deliverables**:
- [ ] RCE vulnerability patched
- [ ] Path traversal fixed
- [ ] `_traction_loop` refactored into services
- [ ] All blocking I/O moved to async

**Blocker**: NO v1.0 until RCE is fixed.

---

### Week 2: STOP THE CREEP
**Goal**: Fix systemic quality issues

**Deliverables**:
- [ ] All bare except clauses removed
- [ ] datetime.utcnow() replaced
- [ ] Dependencies consolidated + pinned
- [ ] CI/CD catches regressions

---

### Week 3: BUILD IT RIGHT
**Goal**: Proper validation, configuration, testing

**Deliverables**:
- [ ] Pydantic validation on all API endpoints
- [ ] Configuration management (no hardcoded values)
- [ ] Security test suite
- [ ] Concurrency tests

---

### Week 4: PROVE IT WORKS
**Goal**: Load testing, documentation update

**Deliverables**:
- [ ] Load test webhook server (100 concurrent)
- [ ] Update all docs to match reality
- [ ] Security audit by external reviewer
- [ ] Performance benchmarks

---

## 🚫 RULES DURING SPRINT

1. **NO NEW FEATURES** - Only bug fixes and refactoring
2. **NO MERGES** - PRs must pass new CI checks
3. **NO EXCEPTIONS** - Fix it right or don't ship it
4. **DAILY REVIEWS** - Check progress against this document

---

## 💬 The Uncomfortable Truth

We marketed this as "professional-grade" when it's barely MVP quality. The architecture is solid, but execution is sloppy.

**Gemini's Verdict**: "It works for local demos, but it is not professional-grade yet."

**My Addition**: And the security holes make it dangerous for production.

---

## ✅ What We're Doing RIGHT

Let's not lose sight of the good:

1. **Vision** - iDesign + State Machine + Prompt Engine concepts are sound
2. **Security Consciousness** - SQL injection protected, HMAC validation
3. **Testing Culture** - We write tests (even if not for the right things)
4. **Documentation** - We document our intent (even if code doesn't match)
5. **Iterative Improvement** - We're doing this review instead of denial

---

## 📝 Sign-Off

**I acknowledge**:
- The gap between vision and reality
- The security vulnerabilities
- The need to stop feature development
- The 4-week commitment to quality

**I commit to**:
- Following this brutal path
- No shortcuts
- Daily progress reviews
- Honesty about blockers

**Signature**: _________________
**Date**: 2026-02-09

---

## 🎓 Learning Resources

**For Security**:
- "Write-Then-Execute" vulnerability pattern
- Path traversal attack vectors (Windows-specific)
- Sandbox escape techniques

**For Architecture**:
- "God Method" antipattern
- Single Responsibility Principle (we claim it, let's live it)
- Async I/O patterns in Python

**For Quality**:
- Exception handling best practices
- Type-driven development with mypy
- Dependency management with pip-tools

---

**Remember**: "Simplify and Reflect. Reflect and Simplify."

We've been adding complexity. Time to ruthlessly simplify.
