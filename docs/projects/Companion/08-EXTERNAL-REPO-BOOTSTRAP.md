# Implementation Plan: External Repo Bootstrap

**Parent**: 01-COMPANION-EXTERNAL-EXTENSION-PLAN.md
**Phase**: 0 (bootstrap, parallel with SDK hardening)
**Depends on**: 02-SDK-PACKAGE-HARDENING (for pip install)
**Estimated Scope**: ~20 files created, ~600 lines

## Problem

Companion must live at `C:\Source\Orket-Extensions\Companion` as an independent external repo with its own package, CI, and release flow. No external extension repo template exists. The Orket side needs authoring tools (validation command, runbook) to support SDK-first external repos.

## Current State

**Exists**:
- `docs/templates/controller_workload_external/` -- minimal template (extension.json + entrypoint)
- `orket_extension_sdk` -- the SDK package (not yet independently installable, see Plan 02)
- Import isolation via AST scan in `workload_loader.py`

**Does NOT exist**:
- Companion repo at `C:\Source\Orket-Extensions\Companion`
- External extension repo template with full structure (pyproject.toml, CI, tests)
- `orket ext validate <path>` CLI command
- `orket ext init <path>` scaffolding command
- Install/validate/run scripts
- Runbook for external extension authoring

## Gap Analysis

| Gap | Severity | Detail |
|-----|----------|--------|
| No Companion repo | BLOCKING | Nothing to build in |
| No full repo template | HIGH | Existing template is minimal (no pyproject, no CI, no tests) |
| No validation CLI command | HIGH | External devs can't validate manifests locally |
| No install/run scripts | HIGH | Plan requires bootstrap scripts |
| No runbook | MEDIUM | No documentation for external extension authoring |
| No CI smoke template | MEDIUM | External repos need CI patterns |

## Implementation Steps

### Step 1: Create Companion repo structure

At `C:\Source\Orket-Extensions\Companion`:

```
Companion/
  extension.yaml              # SDK v0 manifest
  pyproject.toml              # Companion package metadata
  README.md                   # Minimal project description
  src/
    companion_extension/      # Extension entrypoint (installability + manifest compatibility)
      __init__.py
      workload.py             # Thin workload entrypoint for SDK protocol compliance
      config_schema.py        # Companion-owned role/style enums + config models
      config_loader.py        # Load config/modes/*.json
      api_client.py           # Typed host API client (Companion-owned for MVP)
    companion_app/            # Web app
      __init__.py
      server.py               # Single MVP UI serving model (choose one, not multiple)
      static/                 # Built frontend assets
  config/
    modes/
      researcher.json
      programmer.json
      strategist.json
      tutor.json
      supportive_listener.json
      general_assistant.json
    defaults.json             # Extension-level config defaults
    styles/
      platonic.json
      romantic.json
      intermediate.json
  tests/
    conftest.py
    test_config_loading.py
    test_manifest_validation.py
  scripts/
    install.sh                # pip install SDK + Companion deps
    install.ps1               # Windows equivalent
    validate.sh               # Run manifest + import validation
    validate.ps1
    run.sh                    # Start Companion web app
    run.ps1
  .github/
    workflows/
      ci.yml                  # Lint, test, validate manifest
```

### Step 2: extension.yaml

```yaml
manifest_version: v0
extension_id: orket.companion
extension_version: 0.1.0
workloads:
  - workload_id: companion_chat
    entrypoint: companion_extension.workload:CompanionWorkload
    required_capabilities:
      - model.generate
      - memory.write
      - memory.query
    optional_capabilities:
      - speech.transcribe
      - voice.turn_control
```

Voice capabilities are classified as optional/environment-dependent since Companion must work without STT. If manifest semantics do not yet support `optional_capabilities`, note this as a manifest schema gap and list only the required ones.

### Step 3: pyproject.toml

```toml
[project]
name = "orket-companion"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "orket-extension-sdk>=0.1.0",
    "httpx>=0.27",
]

[project.optional-dependencies]
voice = ["faster-whisper>=1.0"]
dev = ["pytest>=8.0", "ruff>=0.5"]
```

### Step 4: Install/validate/run scripts

Both Windows (`.ps1`) and Unix (`.sh`) scripts provided since the target environment requires both.

**install.sh**:
```bash
#!/bin/bash
set -e
pip install orket-extension-sdk  # or path to local SDK wheel
pip install -e ".[dev]"
echo "Companion installed. Run ./scripts/validate.sh to check."
```

**validate.sh**:
```bash
#!/bin/bash
set -e
python -m orket_extension_sdk.validate extension.yaml
python -m orket_extension_sdk.import_scan src/companion_extension/
pytest tests/ -x -q
echo "Validation passed."
```

**run.sh**:
```bash
#!/bin/bash
set -e
echo "Starting Companion web app..."
python -m companion_app.server --port 3000
```

### Step 5: Orket-side validation CLI

`orket ext validate <path>` is Phase 0 required for broader external-authoring support.

`orket ext init <path>` is post-bootstrap convenience; not blocking Companion itself.

Add to `orket/interfaces/cli.py` or new module:

```python
# orket ext validate <path>
def validate_extension(path: Path) -> list[str]:
    """Validate an external extension directory."""
    errors = []
    manifest = find_and_parse_manifest(path)
    if not manifest:
        errors.append("No valid extension manifest found")
        return errors
    schema_errors = validate_manifest_schema(manifest)
    errors.extend(schema_errors)
    for py_file in path.rglob("*.py"):
        import_errors = scan_imports(py_file)
        errors.extend(import_errors)
    for workload in manifest.workloads:
        if not can_resolve_entrypoint(path, workload.entrypoint):
            errors.append(f"Entrypoint not found: {workload.entrypoint}")
    for workload in manifest.workloads:
        for cap in workload.required_capabilities:
            if cap not in _CAPABILITY_VOCAB:
                errors.append(f"Unknown capability: {cap}")
    return errors
```

### Step 6: SDK-side validation module

Validation and import-scan tools must run without requiring the orket package to be importable.

```python
# orket_extension_sdk/validate.py (runnable: python -m orket_extension_sdk.validate <manifest>)
# orket_extension_sdk/import_scan.py (runnable: python -m orket_extension_sdk.import_scan <dir>)
```

These are pure stdlib tools. No orket internals required.

### Step 7: Runbook document

Create `docs/guides/external-extension-authoring.md` in the Orket repo:
- Prerequisites (Python 3.11+, SDK installed)
- Repo structure convention
- Manifest format
- Capability registration
- Config directory convention
- Testing patterns (unit, contract, integration)
- Validation workflow
- Common errors and fixes

### Step 8: CI template for external repos

```yaml
name: CI
on: [push, pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install orket-extension-sdk
      - run: python -m orket_extension_sdk.validate extension.yaml
      - run: python -m orket_extension_sdk.import_scan src/
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -x -q
```

## Acceptance Criteria

1. Companion repo at `C:\Source\Orket-Extensions\Companion` initializes, installs, validates, runs
2. `extension.yaml` parses and validates against SDK manifest schema
3. Import scan passes -- no `orket.*` internal imports in `src/companion_extension/`
4. `scripts/install.sh` (and `.ps1`) installs all deps in a clean venv
5. `scripts/validate.sh` runs manifest check, import scan, and tests
6. `orket ext validate <path>` works from the Orket CLI
7. Validation tools run without orket package installed
8. CI workflow passes on push
9. External repo is treated as the source of truth for Companion development, not an afterthought

## Files to Create/Modify

**Orket repo**:
| Action | Path |
|--------|------|
| CREATE | `orket_extension_sdk/validate.py` |
| CREATE | `orket_extension_sdk/import_scan.py` |
| MODIFY | `orket/interfaces/cli.py` (add ext validate subcommand) |
| CREATE | `docs/guides/external-extension-authoring.md` |
| CREATE | `docs/templates/external_extension/` (full template directory) |

**Companion repo** (new):
| Action | Path |
|--------|------|
| CREATE | `C:\Source\Orket-Extensions\Companion\` (entire repo) |
