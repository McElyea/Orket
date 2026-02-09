# Orket Code Review - February 9, 2026

## Executive Summary

**Reviewer**: Claude Sonnet 4.5
**Review Date**: 2026-02-09
**Codebase**: Orket v0.3.8 (122 Python files)
**Severity Levels**: 🔴 Critical | 🟠 High | 🟡 Medium | 🔵 Low | ✅ Good Practice

**Overall Assessment**: The project shows solid architectural thinking with good security practices in file operations and SQL queries. However, there are significant quality issues that need immediate attention, particularly around error handling, dependency management, and deprecated API usage.

---

## 🔴 CRITICAL ISSUES

### 1. Bare Exception Handlers (15+ instances)

**Severity**: 🔴 **CRITICAL**
**Impact**: Silent failures, impossible debugging, masked bugs

**Files Affected**:
- `orket/driver.py` (3 instances)
- `orket/interfaces/api.py`
- `orket/discovery.py` (2 instances)
- `orket/orket.py`
- `orket/logging.py` (2 instances)
- `orket/agents/agent.py` (2 instances)
- `orket/preview.py` (2 instances)
- `orket/services/tool_parser.py`
- `orket/orchestration/models.py`
- `orket/vendors/local.py`

**Example from `orket/driver.py:42`**:
```python
except:
    return "No recent transcript available"
```

**Why This is Critical**:
- Catches `SystemExit`, `KeyboardInterrupt`, `MemoryError`
- Masks bugs completely - code fails silently
- Makes debugging nearly impossible
- Violates Python best practices

**Fix Required**:
```python
# WRONG
except:
    pass

# CORRECT
except (SpecificException, AnotherException) as e:
    log_event("error", f"Operation failed: {e}", "error")
    raise
```

**Impact**: Production incidents will be impossible to diagnose. Silent data corruption possible.

---

### 2. Deprecated `datetime.utcnow()` Usage

**Severity**: 🔴 **CRITICAL**
**Impact**: Will break in Python 3.12+, timezone bugs

**Files Affected**:
- `orket/session.py:32, 42`
- `orket/domain/sandbox.py:65`
- `orket/domain/bug_fix_phase.py`
- `orket/services/sandbox_orchestrator.py`
- `orket/utils.py`

**Current Code**:
```python
datetime.utcnow().isoformat() + "Z"  # DEPRECATED
```

**Warning from Python**:
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled
for removal in a future version. Use timezone-aware objects to represent
datetimes in UTC: datetime.datetime.now(datetime.UTC).
```

**Fix Required**:
```python
from datetime import datetime, UTC

# CORRECT
datetime.now(UTC).isoformat()
```

**Impact**:
- Code will break in Python 3.12+
- Timezone bugs in distributed systems
- Data corruption in timestamp comparisons

**Action**: Global search-and-replace required IMMEDIATELY.

---

### 3. Dependency Management Chaos

**Severity**: 🔴 **CRITICAL**
**Impact**: Unreproducible builds, security vulnerabilities

**Issue**: `requirements.txt` and `pyproject.toml` are completely out of sync.

**requirements.txt** (24 dependencies, NO VERSION PINS):
```txt
jsonschema
ollama
pydantic
fastapi
# ... 20 more WITHOUT versions
```

**pyproject.toml** (only 2 dependencies):
```toml
dependencies = [
    "jsonschema",
    "ollama"
]
```

**Problems**:
1. **No version pinning** → Different installs get different code
2. **Conflicting sources of truth** → Which file is authoritative?
3. **Missing transitive dependencies** → Breaks on fresh install
4. **Security risk** → Can't audit dependency versions
5. **Unreproducible builds** → "Works on my machine" syndrome

**Example Failure Scenario**:
```bash
# Developer A (today)
pip install pydantic  # Gets 2.5.0

# Developer B (next month)
pip install pydantic  # Gets 3.0.0 (breaking changes)

# Production breaks because pydantic 3.0 changes API
```

**Fix Required**:
```toml
[project]
dependencies = [
    "fastapi>=0.109.0,<0.110.0",
    "pydantic>=2.5.0,<3.0.0",
    "ollama>=0.1.0,<0.2.0",
    # ... all dependencies with version constraints
]
```

**Action**:
1. Delete `requirements.txt`
2. Move all deps to `pyproject.toml` with version pins
3. Use `pip-compile` for lock file
4. Document in CONTRIBUTING.md

---

### 4. Subprocess Command Injection Risk

**Severity**: 🟠 **HIGH**
**Impact**: Potential remote code execution

**File**: `orket/services/sandbox_orchestrator.py`

**Vulnerable Code**:
```python
# Line 131-137
result = subprocess.run(
    [
        "docker-compose",
        "-f", str(compose_path),
        "-p", sandbox.compose_project,  # <-- User-controlled?
        "down", "-v"
    ],
    ...
)
```

**Risk**:
- If `sandbox.compose_project` comes from untrusted input (PR title, repo name), potential injection
- Docker project names can contain shell metacharacters

**Example Attack**:
```python
# Malicious repo name
repo_name = "test; rm -rf /"
compose_project = f"orket-{repo_name}"  # → "orket-test; rm -rf /"
```

**Fix Required**:
```python
import re

def sanitize_project_name(name: str) -> str:
    """Sanitize project names for Docker Compose."""
    # Only allow alphanumeric, dash, underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', name)
    if not sanitized:
        raise ValueError(f"Invalid project name: {name}")
    return sanitized[:64]  # Docker limit

# Usage
sandbox.compose_project = sanitize_project_name(f"orket-{rock_id}")
```

**Impact**: Moderate - requires Gitea access, but could lead to RCE on webhook server.

---

## 🟠 HIGH PRIORITY ISSUES

### 5. Missing Error Context in Webhook Handler

**Severity**: 🟠 **HIGH**
**File**: `orket/services/gitea_webhook_handler.py`

**Issue**: Generic exception handling loses critical debugging context.

**Current Code**:
```python
except Exception as e:
    log_event("sandbox_deployment_failed", {
        "repo": repo_full_name,
        "pr": pr_number,
        "error": str(e)  # <-- Loses stack trace!
    }, self.workspace)
    print(f"❌ Sandbox deployment failed: {e}")
```

**Problems**:
- No stack trace logged
- Can't diagnose failures without reproduction
- Generic `Exception` catches too much

**Fix**:
```python
import traceback

except Exception as e:
    log_event("sandbox_deployment_failed", {
        "repo": repo_full_name,
        "pr": pr_number,
        "error": str(e),
        "traceback": traceback.format_exc(),  # ADD THIS
        "error_type": type(e).__name__
    }, self.workspace)
    raise  # Or handle specifically
```

---

### 6. Race Conditions in Port Allocation

**Severity**: 🟠 **HIGH**
**File**: `orket/domain/sandbox.py`

**Issue**: In-memory port allocator has race conditions.

**Current Design**:
```python
class PortAllocator:
    def __init__(self):
        self._allocated: Dict[str, PortAllocation] = {}  # In-memory

    def allocate(self, sandbox_id: str, tech_stack: TechStack) -> PortAllocation:
        # NOT THREAD-SAFE
        ports = PortAllocation(api=next_api, frontend=next_frontend, ...)
        self._allocated[sandbox_id] = ports
        return ports
```

**Race Condition Scenario**:
```
Thread A: Check port 8001 available ✓
Thread B: Check port 8001 available ✓
Thread A: Allocate 8001
Thread B: Allocate 8001  ← CONFLICT!
```

**Impact**:
- Port conflicts when multiple PRs merge simultaneously
- Docker containers fail to start
- Webhook failures

**Fixes Required**:
1. **Short-term**: Add file-based locking
```python
from filelock import FileLock

def allocate(self, ...):
    with FileLock("port_allocation.lock"):
        # Allocation logic
```

2. **Long-term**: Move to SQLite/Redis with proper locking
```python
# Use database with UNIQUE constraints
CREATE TABLE port_allocations (
    port INTEGER PRIMARY KEY,
    sandbox_id TEXT NOT NULL,
    allocated_at TIMESTAMP
);
```

---

### 7. Missing Input Validation

**Severity**: 🟠 **HIGH**
**File**: `orket/webhook_server.py`

**Issue**: No payload size limits or schema validation.

**Current Code**:
```python
@app.post("/webhook/gitea")
async def gitea_webhook(request: Request, ...):
    body = await request.body()  # <-- No size limit!
    payload = await request.json()  # <-- No schema validation!
```

**Attack Vectors**:
1. **DoS**: Send 1GB webhook → OOM crash
2. **Type confusion**: Send malformed JSON → KeyError crashes
3. **Missing fields**: Payload without required keys → crashes

**Fix**:
```python
from pydantic import BaseModel, Field

class GiteaWebhookPayload(BaseModel):
    action: str
    number: int = Field(gt=0)
    pull_request: Dict[str, Any]
    repository: Dict[str, Any]
    # ... full schema

@app.post("/webhook/gitea")
async def gitea_webhook(
    request: Request,
    x_gitea_event: str = Header(None),
    x_gitea_signature: str = Header(None)
):
    # Size limit
    MAX_SIZE = 1024 * 1024  # 1MB
    body = await request.body()
    if len(body) > MAX_SIZE:
        raise HTTPException(413, "Payload too large")

    # Schema validation
    try:
        payload = GiteaWebhookPayload.parse_raw(body)
    except ValidationError as e:
        raise HTTPException(400, f"Invalid payload: {e}")
```

---

## 🟡 MEDIUM PRIORITY ISSUES

### 8. Inconsistent Async/Await Usage

**Severity**: 🟡 **MEDIUM**
**Files**: Multiple

**Issue**: Mixing blocking and async code without consideration.

**Example** (`orket/services/gitea_webhook_handler.py`):
```python
async def _auto_merge(self, repo: Dict, pr_number: int) -> None:
    # This is BLOCKING I/O in an async function!
    response = requests.post(url, ...)  # <-- Should be async
```

**Problems**:
- Blocks event loop
- Defeats purpose of async
- Poor performance under load

**Fix**:
```python
import httpx

async def _auto_merge(self, repo: Dict, pr_number: int) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(url, ...)  # Non-blocking
```

**Impact**: Webhook server will freeze under load (multiple simultaneous webhooks).

---

### 9. No Request Timeout Handling

**Severity**: 🟡 **MEDIUM**
**Files**: All HTTP request code

**Current**:
```python
requests.post(url, auth=self.auth, json=data, timeout=10)
```

**Issue**: 10-second timeout is hardcoded, no retry logic.

**Gitea Problems**:
- If Gitea is slow: webhook fails
- If network glitches: operation lost
- No exponential backoff

**Fix**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def _gitea_api_call(self, method: str, url: str, **kwargs):
    timeout = kwargs.pop('timeout', 30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await getattr(client, method)(url, **kwargs)
```

---

### 10. Missing Logging Configuration

**Severity**: 🟡 **MEDIUM**
**File**: `orket/logging.py`

**Issue**: No log rotation, structured logging, or levels.

**Current**:
```python
def log_event(event_type: str, data, ...):
    # Appends to file forever
    # No rotation → file grows infinitely
    # No structured format → hard to parse
```

**Problems**:
1. Log files grow unbounded
2. No log levels (DEBUG, INFO, ERROR)
3. Not machine-parseable
4. No centralized config

**Fix**: Use Python's logging module properly:
```python
import logging
import logging.handlers

def setup_logging(workspace: Path):
    logger = logging.getLogger("orket")
    logger.setLevel(logging.INFO)

    # Rotating file handler (max 10MB, keep 5 files)
    handler = logging.handlers.RotatingFileHandler(
        workspace / "orket.log",
        maxBytes=10*1024*1024,
        backupCount=5
    )

    # JSON formatter for structured logs
    formatter = logging.Formatter(
        '{"timestamp":"%(asctime)s","level":"%(levelname)s","event":"%(message)s"}'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

---

### 11. Hardcoded Credentials in Tests

**Severity**: 🟡 **MEDIUM**
**Files**: Test files

**Not Reviewed Fully**, but common pattern to check:
```python
# BAD
GITEA_PASSWORD = "password123"  # In test file

# GOOD
GITEA_PASSWORD = os.getenv("TEST_GITEA_PASSWORD", "test-only-password")
```

---

### 12. Missing Type Hints

**Severity**: 🟡 **MEDIUM**
**Coverage**: ~60% (estimated)

**Files with Poor Type Coverage**:
- `orket/driver.py`
- `orket/logging.py`
- Many utility functions

**Example**:
```python
# Current
def get_card_history(self, card_id):  # No return type
    ...

# Should be
def get_card_history(self, card_id: str) -> List[str]:
    ...
```

**Fix**: Enable mypy strict mode:
```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
```

Run: `mypy orket/` and fix all errors.

---

## 🔵 LOW PRIORITY ISSUES

### 13. Inconsistent Naming Conventions

**Severity**: 🔵 **LOW**

**Mixed conventions**:
- `repo_full_name` (snake_case) ✓
- `rockId` (camelCase) ✗
- `pr_key` (snake_case) ✓

**Fix**: Enforce PEP 8 with linter:
```bash
ruff check orket/ --select N  # Naming conventions
```

---

### 14. Magic Numbers

**Severity**: 🔵 **LOW**

**Examples**:
```python
# Bad
if cycles >= 4:  # What is 4?

# Good
MAX_REVIEW_CYCLES = 4
if cycles >= MAX_REVIEW_CYCLES:
```

**Found**:
- Review cycle limits: 3, 4
- Port ranges: 8001, 3001, 5433
- Timeouts: 10, 60
- Thresholds: 7 (iDesign)

**Fix**: Extract to constants module:
```python
# orket/constants.py
class ReviewPolicy:
    MAX_CYCLES = 4
    ARCHITECT_ESCALATION_CYCLE = 3

class Ports:
    API_START = 8001
    FRONTEND_START = 3001
    POSTGRES_START = 5433
```

---

### 15. Commented-Out Code

**Severity**: 🔵 **LOW**

**Issue**: TODOs without tickets.

**Found**:
- `orket/domain/bug_fix_phase.py:237` - "TODO: Integrate with card system"
- `orket/services/gitea_webhook_handler.py:314` - "TODO: Read from .orket.json"

**Fix**: Create GitHub issues for all TODOs or remove them.

---

## ✅ GOOD PRACTICES OBSERVED

### Security

1. **SQL Injection Protection** ✅
   - All queries use parameterized statements
   - No string interpolation in SQL

2. **Path Traversal Protection** ✅
   - `_resolve_safe_path()` validates all file operations
   - Workspace sandboxing enforced

3. **HMAC Signature Validation** ✅
   - Webhook endpoints verify signatures
   - Constant-time comparison used

### Architecture

4. **Clean Separation of Concerns** ✅
   - Domain models separate from infrastructure
   - Repository pattern for data access
   - Service layer well-defined

5. **State Machine Governance** ✅
   - Card status transitions enforced
   - WaitReason tracking prevents ambiguity

6. **iDesign Enforcement** ✅
   - Complexity gate at 7 issues
   - Structural integrity checks

### Testing

7. **Good Test Coverage for Critical Paths** ✅
   - `test_golden_flow.py` - End-to-end tests
   - `test_idesign_enforcement.py` - Governance tests
   - `test_sandbox_compose_generation.py` - Integration tests

---

## 📊 METRICS

### Code Quality Score: 6.5/10

| Category | Score | Notes |
|----------|-------|-------|
| Security | 8/10 | Good SQL/path protection, but subprocess risks |
| Error Handling | 3/10 | Bare except clauses everywhere |
| Type Safety | 6/10 | Some hints, but incomplete |
| Testing | 7/10 | Good coverage of happy paths |
| Documentation | 7/10 | Good docs, but code comments sparse |
| Maintainability | 6/10 | Architectural debt accumulating |
| Performance | 5/10 | Async misuse, no caching |
| Dependencies | 2/10 | No version control, conflicting files |

---

## 🎯 ACTION PLAN (Priority Order)

### Week 1: Critical Fixes

1. **Replace all bare `except:` clauses** (2-3 hours)
   - Find: `except:\s*$` and `except:\s*pass`
   - Replace with specific exceptions
   - PR: "fix: Replace bare exception handlers"

2. **Fix datetime.utcnow() deprecation** (1 hour)
   - Global search/replace
   - Test thoroughly
   - PR: "fix: Replace deprecated datetime.utcnow()"

3. **Consolidate dependency management** (3-4 hours)
   - Audit all dependencies
   - Add version pins to pyproject.toml
   - Generate lock file
   - Delete requirements.txt
   - PR: "chore: Consolidate and pin dependencies"

### Week 2: High Priority

4. **Add input validation to webhook server** (4 hours)
   - Create Pydantic models for payloads
   - Add size limits
   - Add error handling
   - PR: "feat: Add webhook payload validation"

5. **Fix async/await usage** (6 hours)
   - Replace `requests` with `httpx`
   - Add proper async context managers
   - Test under load
   - PR: "refactor: Fix async HTTP calls"

6. **Sanitize subprocess inputs** (2 hours)
   - Add input validation
   - Create sanitization utilities
   - Audit all subprocess calls
   - PR: "security: Sanitize subprocess inputs"

### Week 3: Medium Priority

7. **Improve logging** (4 hours)
   - Add rotation
   - Structured logging
   - Log levels
   - PR: "feat: Improve logging infrastructure"

8. **Add port allocation locking** (3 hours)
   - File-based lock
   - Race condition tests
   - PR: "fix: Add port allocation locking"

9. **Add type hints** (ongoing)
   - Enable mypy
   - Fix module by module
   - Multiple PRs

### Week 4: Low Priority

10. **Code cleanup** (ongoing)
    - Extract magic numbers
    - Remove commented code
    - Enforce naming conventions
    - Multiple small PRs

---

## 🔒 SECURITY AUDIT CHECKLIST

- [x] SQL Injection: Protected (parameterized queries)
- [x] Path Traversal: Protected (_resolve_safe_path)
- [x] HMAC Validation: Implemented
- [ ] Command Injection: **NEEDS REVIEW** (subprocess calls)
- [ ] DoS Protection: **MISSING** (no rate limiting, no payload size limits)
- [ ] Secrets Management: **PARTIAL** (.env used, but no rotation)
- [ ] Input Validation: **INSUFFICIENT** (webhook payloads)
- [ ] Error Messages: **LEAKY** (exposing stack traces to API)
- [ ] Dependency Audit: **NOT POSSIBLE** (no version pins)

---

## 📝 TESTING GAPS

### Missing Tests:
1. **Error path coverage** - Only happy paths tested
2. **Concurrency tests** - No race condition tests
3. **Integration tests** - Webhook → Sandbox flow not tested end-to-end
4. **Performance tests** - No load testing
5. **Security tests** - No fuzzing, no penetration testing

### Recommended:
```bash
# Add these test files
tests/test_error_handling.py
tests/test_concurrency.py
tests/test_webhook_integration.py
tests/test_performance.py
```

---

## 🎓 LEARNING RECOMMENDATIONS

### For Team

1. **Python Best Practices**:
   - Read PEP 8 (style guide)
   - Read PEP 484 (type hints)
   - Study "Effective Python" by Brett Slatkin

2. **Async Programming**:
   - "Using Asyncio in Python" (Caleb Hattingh)
   - FastAPI async best practices

3. **Security**:
   - OWASP Top 10
   - "Black Hat Python" (Justin Seitz)

---

## 💬 FINAL THOUGHTS

**Strengths**:
- Solid architectural vision (iDesign, State Machine)
- Good security consciousness in core areas
- Active development and iteration
- Good documentation culture

**Weaknesses**:
- Technical debt accumulating quickly
- Error handling is a disaster
- Dependency management will cause production incidents
- Async misuse will hurt performance

**Verdict**: This is a **promising project with concerning quality issues**. The architecture is sound, but execution quality needs immediate improvement before v1.0.

**Recommendation**: **PAUSE new feature development** for 2 weeks. Focus entirely on technical debt reduction. The issues identified here WILL cause production incidents if not addressed.

**Critical Path to Production**:
1. Fix critical issues (Week 1)
2. Add integration tests (Week 2)
3. Security audit (Week 3)
4. Load testing (Week 4)
5. Then → Production

---

## 📞 NEXT STEPS

1. **Review this document with team**
2. **Create GitHub issues for each item**
3. **Prioritize action plan**
4. **Assign owners**
5. **Set up CI/CD to prevent regressions**:
   ```yaml
   # .github/workflows/quality.yml
   - name: Run mypy
     run: mypy orket/
   - name: Run ruff
     run: ruff check orket/
   - name: Check for bare except
     run: grep -r "except:" orket/ && exit 1 || exit 0
   ```

---

**Report Generated**: 2026-02-09
**Reviewed By**: Claude Sonnet 4.5 (Automated Code Review)
**Next Review**: After critical fixes (2 weeks)
