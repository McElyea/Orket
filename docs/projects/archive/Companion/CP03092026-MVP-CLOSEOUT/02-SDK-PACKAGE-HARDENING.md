# Implementation Plan: SDK Package Hardening

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 0 (prerequisite for all other plans)
**Estimated Scope**: ~15 files touched, ~400 lines changed

## Problem

`orket_extension_sdk` is currently a subdirectory inside the main `orket` monorepo with no independent `pyproject.toml`. It cannot be `pip install`-ed from an external repo. The Companion plan requires it as an independently installable, versioned authority package.

## Current State

- Package lives at `orket_extension_sdk/` in the monorepo root
- Exports: manifest, workload, capabilities, result, controller, audio, piper_tts, llm, tui, testing
- Version currently exposed from `orket_extension_sdk.__version__`; needs single-source authority
- No `pyproject.toml` for the SDK subdirectory
- Main repo packaging currently treats the SDK as an in-repo package rather than an independently installable authority package
- Import isolation in `workload_loader.py` blocks `orket.*` internals but allows `orket.extensions`

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No independent pyproject.toml | BLOCKING | External repos cannot `pip install orket-extension-sdk` |
| No version pinning contract | HIGH | No SemVer policy; breaking changes invisible to consumers |
| No publish/release workflow | HIGH | No CI job to build + publish the SDK wheel |
| Piper TTS pulls ONNX runtime | MEDIUM | Heavy optional dep bundled unconditionally in SDK |
| `testing.py` imports may pull internal deps | MEDIUM | FakeCapabilities may transitively import orket internals |

## Implementation Steps

### Step 1: Single-source version authority
- Create `orket_extension_sdk/__version__.py` containing `__version__ = "0.1.0"`
- Re-export from `orket_extension_sdk/__init__.py`: `from orket_extension_sdk.__version__ import __version__`
- `pyproject.toml` reads version via `dynamic = ["version"]` sourced from `__version__.py`

### Step 2: Create SDK-local pyproject.toml
- Create `orket_extension_sdk/pyproject.toml` with:
  - `name = "orket-extension-sdk"`
  - `dynamic = ["version"]`, version sourced from `orket_extension_sdk.__version__`
  - `[project.optional-dependencies]` for `tts` (onnxruntime, numpy) and `testing` extras
  - Minimal dependencies: `pydantic >= 2.0`, `pyyaml`
  - Python requires `>= 3.11`
- Add `orket_extension_sdk/README.md` (minimal, describes external-consumer intent)
- Create `orket_extension_sdk/py.typed` and include it in package data for PEP 561 consumer typing support

### Step 3: Validate zero internal imports
- Run AST scan on every `.py` file under `orket_extension_sdk/`
- Confirm no `import orket.` or `from orket.` statements exist
- Add CI check: `python -c "import ast, pathlib; ..."` that fails on internal imports
- Fix any transitive leaks (especially in `testing.py`)

### Step 4: Version contract
- Adopt SemVer: `0.x.y` means unstable API, `1.0.0` means stable contract
- Add `CHANGELOG.md` in SDK root (empty template with Unreleased section)
- One packaging authority for SDK version: `__version__.py` is the single source

### Step 5: Build and local install test
- `cd orket_extension_sdk && pip install -e .` must succeed in a clean venv
- `cd orket_extension_sdk && pip install -e ".[tts,testing]"` must pull optional deps
- Create `tests/sdk/test_sdk_install_isolation.py`: import SDK in subprocess with no orket on sys.path

### Step 6: CI publish workflow
- Add GitHub Actions job (or equivalent) that builds wheel on tag `sdk-v*`
- Publish to private PyPI or local wheelhouse (not public PyPI for now)
- Add `orket_extension_sdk/Makefile` or script: `build`, `test`, `publish`
- Add clean-venv install test in CI

### Step 7: Update monorepo development flow
- Update monorepo development/install flow so root editable installs continue to work while preserving SDK independent packaging authority
- Avoid introducing circular packaging assumptions between the main package and SDK package
- Ensure `pip install -e .` at monorepo root still works

## Acceptance Criteria

1. `pip install orket_extension_sdk/` succeeds in a clean venv with only stdlib + pydantic + pyyaml
2. `from orket_extension_sdk import ExtensionManifest, Workload, CapabilityRegistry` works
3. No `orket.*` imports anywhere in SDK source (verified by CI)
4. Version string accessible: `orket_extension_sdk.__version__`
5. Optional extras (`tts`, `testing`) install cleanly without pulling orket internals
6. `python -c "import orket_extension_sdk; print(orket_extension_sdk.__version__)"` succeeds in a clean venv with no orket package import required
7. `py.typed` marker present for PEP 561 support

## Files to Create/Modify

| Action | Path |
|--------|------|
| CREATE | `orket_extension_sdk/pyproject.toml` |
| CREATE | `orket_extension_sdk/__version__.py` |
| CREATE | `orket_extension_sdk/py.typed` |
| CREATE | `orket_extension_sdk/README.md` |
| CREATE | `orket_extension_sdk/CHANGELOG.md` |
| MODIFY | `orket_extension_sdk/__init__.py` (re-export version from __version__.py) |
| MODIFY | `orket_extension_sdk/testing.py` (audit imports) |
| MODIFY | `pyproject.toml` (update dev install flow, avoid circular dep) |
| CREATE | `tests/sdk/test_sdk_install_isolation.py` |
| CREATE | `.github/workflows/sdk-publish.yml` or equivalent |
