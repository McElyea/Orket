# Implementation Plan: Import Isolation Hardening

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 1 (SDK/host seam hardening)
**Depends on**: 02-SDK-PACKAGE-HARDENING
**Estimated Scope**: ~5 files touched, ~200 lines added

## Problem

The plan requires both static import scan AND runtime enforcement to pass. Currently only AST-based static scan exists (`workload_loader.py`). There is no runtime guard. Also, the import allowlist needs to be formalized: stdlib, SDK modules, and third-party deps declared in Companion package/manifest authority.

## Current State

**Static scan** (`orket/extensions/workload_loader.py` `validate_extension_imports()`):
- AST-based scan of `import X` and `from X import Y`
- Blocks 11 `orket.*` internal prefixes
- Allows `orket.extensions` imports
- Runs at load time

**No runtime guard**:
- After static validation, loaded modules can dynamically import anything
- `importlib.import_module("orket.orchestration")` would succeed at runtime
- No `sys.meta_path` hook or sandbox

**Import allowlist** not formalized:
- No manifest field for `allowed_imports` or `declared_dependencies`
- No validation that extension only imports what it declares

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No runtime import guard | HIGH | Dynamic imports bypass static scan |
| No CI-integrated scan for external repos | MEDIUM | External repos need standalone scan tool |
| `orket.extensions` allowed surface needs review | MEDIUM | May leak internal runtime behavior |
| Static scan doesn't cover subprocesses | LOW | Edge case, out of scope for MVP |

## Implementation Steps

### Step 1: Runtime import guard via modern import hooks

Use `find_spec`-based interception (PEP 302/451 modern protocol), not legacy `find_module`/`load_module`.

```python
# orket/extensions/import_guard.py

import importlib.abc
import importlib.machinery

class ExtensionImportGuard(importlib.abc.MetaPathFinder):
    """
    Meta path finder that blocks orket.* internal imports during extension execution.
    Installed on sys.meta_path during workload.run() and removed after.
    """
    BLOCKED_PREFIXES = (
        "orket.orchestration",
        "orket.decision_nodes",
        "orket.runtime",
        "orket.application",
        "orket.adapters",
        "orket.interfaces",
        "orket.services",
        "orket.kernel",
        "orket.core",
        "orket.webhook_server",
    )

    ALLOWED_PREFIXES = (
        "orket_extension_sdk",
    )

    def find_spec(self, fullname: str, path=None, target=None):
        if any(fullname.startswith(p) for p in self.ALLOWED_PREFIXES):
            return None  # allow normal import
        if any(fullname.startswith(p) for p in self.BLOCKED_PREFIXES):
            raise ImportError(
                f"Extension import blocked: '{fullname}' is an internal Orket module. "
                f"Extensions must use the SDK or host API seam."
            )
        return None  # allow everything else
```

**Note on `orket.extensions`**: Re-evaluate whether this remains an allowed import surface. If any internal runtime behavior leaks through that namespace, it should not remain broadly allowed. For now, it is **removed from the allowlist** -- extensions should use `orket_extension_sdk` exclusively. If specific `orket.extensions` imports are needed, they must be audited and explicitly re-allowed.

### Step 2: Guard lifecycle management

Guard scope: in-process Python import enforcement only during extension workload execution. Subprocess/import escape is out of scope unless separately handled.

```python
class ImportGuardContext:
    """
    Context manager that installs the import guard during extension execution
    and removes it after, regardless of success or failure.
    """
    def __init__(self):
        self._guard = ExtensionImportGuard()

    def __enter__(self):
        sys.meta_path.insert(0, self._guard)
        return self

    def __exit__(self, *exc):
        try:
            sys.meta_path.remove(self._guard)
        except ValueError:
            pass  # already removed
```

Wire into `WorkloadExecutor.run_sdk_workload()`:
```python
with ImportGuardContext():
    result = await workload.run(ctx, payload)
```

Runtime enforcement must not affect non-extension host/runtime operation outside the guard context.

### Step 3: Standalone scan tool for external repos

```python
# orket_extension_sdk/import_scan.py
# Runnable: python -m orket_extension_sdk.import_scan src/

"""
Scans all .py files in the given directory for blocked imports.
Returns exit code 0 if clean, 1 if violations found.
Does NOT require orket to be installed -- uses hardcoded blocked prefix list.
Pure stdlib implementation.
"""
```

This is a truth guard for external-consumer validation, not merely a lint rule. Usable in CI with only stdlib.

### Step 4: Declared-import allowlisting (deferred)

Treat declared-import allowlisting as optional future hardening. It is not required strongly enough to justify manifest-contract expansion in MVP. If added later:

```yaml
workloads:
  - workload_id: companion_chat
    declared_imports:  # optional, future
      - httpx
      - pydantic
      - companion_extension
```

### Step 5: Test coverage

- Test static scan catches `import orket.orchestration`
- Test static scan catches `from orket.runtime import X`
- Test runtime guard blocks `importlib.import_module("orket.orchestration")` during extension execution
- Test runtime guard allows `import orket_extension_sdk`
- Test runtime guard does NOT block imports outside extension execution context
- Test guard is removed after workload execution (no leaked global state)
- Test standalone scan tool works without orket installed

## Acceptance Criteria

1. Static scan blocks all internal prefixes (existing, verified)
2. Runtime guard blocks dynamic imports of internal modules during extension execution
3. Runtime guard is installed only during workload execution, not globally
4. Runtime guard allows SDK and stdlib imports
5. Runtime guard removal is tested -- no leaked global state
6. Standalone import scan tool works in external repo CI without orket installed (stdlib only)
7. MVP acceptance: both static scan and runtime enforcement pass
8. Runtime import enforcement blocks dynamic internal imports during extension execution without affecting non-extension host/runtime operation outside the guard context

## Files to Create/Modify

| Action | Path |
|--------|------|
| CREATE | `orket/extensions/import_guard.py` |
| MODIFY | `orket/extensions/workload_executor.py` (wrap run in ImportGuardContext) |
| CREATE | `orket_extension_sdk/import_scan.py` (standalone tool, stdlib only) |
| CREATE | `tests/integration/test_import_guard_runtime.py` |
| CREATE | `tests/integration/test_import_guard_no_leak.py` |
| CREATE | `tests/sdk/test_import_scan_standalone.py` |
