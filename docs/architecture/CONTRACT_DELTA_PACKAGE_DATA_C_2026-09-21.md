# Package resource completeness

Status: Active contract delta
Last updated: 2026-09-21
Owner: Orket Core

The core distribution includes the existing `orket/permissions.json`,
`orket/permissions.schema.json` and `orket/kernel/v1/odr/artifact.schema.json`
through explicit package-data entries in `pyproject.toml`. Their authored bytes
are unchanged. The wheel and source archive retain all tracked non-Python files
under `orket/`; clean-build regression coverage compares actual resource bytes.

Installed callers can read these resources through `importlib.resources`
independently of the working directory. The permission example must validate
against its shipped schema; both shipped schemas must validate as JSON Schema.
Availability does not activate the permission example as runtime authorization,
add a policy reader, or promote the ODR schema to completion-verifier authority.
Existing consumers, project-root selection and admission behavior remain unchanged.

This fixes the three-resource package ceiling retained at the .44 checkpoint.
Artifact inventory and installed-resource reads establish packaging completeness
for the enumerated tracked files, not alias-complete runtime reachability or
support for arbitrary external assets. The canonical remediation plan owns the
observed source/installed cells and remaining Linux, D/E/CAP and acceptance gaps.
