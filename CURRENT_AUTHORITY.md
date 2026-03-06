# CURRENT_AUTHORITY.md

Last updated: 2026-03-06

This file is the current canonical authority snapshot for high-impact runtime and governance paths.

It is intentionally narrow:
1. Agent behavior rules remain in `AGENTS.md`.
2. Contributor workflow rules remain in `docs/CONTRIBUTOR.md`.
3. This file tracks what is authoritative right now.

This file does not define:
1. all supported features,
2. all experimental surfaces,
3. all repository conventions.

It defines only the currently authoritative paths that agents and contributors must treat as canonical unless explicitly directed otherwise.

## Current Canonical Paths

1. Install/bootstrap: `python -m pip install -e ".[dev]"`
2. Default runtime: `python main.py`
3. Named rock runtime: `python main.py --rock <rock_name>`
4. API runtime: `python server.py`
5. Canonical test command: `python -m pytest -q`
6. Active docs index: `docs/README.md`
7. Active roadmap: `docs/ROADMAP.md`
8. Active contributor workflow: `docs/CONTRIBUTOR.md`
9. Published artifact index: `benchmarks/published/index.json`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-03-06",
  "authority": {
    "dependency_authority": {
      "primary": "pyproject.toml",
      "install_command": "python -m pip install -e \".[dev]\"",
      "sources": [
        "pyproject.toml",
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "install_bootstrap": {
      "commands": [
        "python -m pip install --upgrade pip",
        "python -m pip install -e \".[dev]\""
      ],
      "sources": [
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "runtime_entrypoints": {
      "cli_default": "python main.py",
      "cli_named_rock": "python main.py --rock <rock_name>",
      "api": "python server.py",
      "sources": [
        "docs/CONTRIBUTOR.md",
        "README.md"
      ]
    },
    "canonical_test_command": {
      "command": "python -m pytest -q",
      "lane_reference": "docs/TESTING_POLICY.md",
      "sources": [
        "docs/CONTRIBUTOR.md",
        "docs/RUNBOOK.md",
        "docs/TESTING_POLICY.md"
      ]
    },
    "verification_policy": {
      "agent_policy": "AGENTS.md",
      "contributor_policy": "docs/CONTRIBUTOR.md",
      "testing_policy": "docs/TESTING_POLICY.md",
      "sources": [
        "AGENTS.md",
        "docs/CONTRIBUTOR.md",
        "docs/TESTING_POLICY.md"
      ]
    },
    "active_spec_index": {
      "root_docs_index": "docs/README.md",
      "active_roadmap_source": "docs/ROADMAP.md",
      "process_source": "docs/CONTRIBUTOR.md",
      "local_prompting_contract_source": "docs/projects/protocol-governed/local-prompting-requirements.md",
      "sources": [
        "docs/README.md",
        "docs/ROADMAP.md"
      ]
    },
    "canonical_script_output_locations": {
      "published_artifacts_index": "benchmarks/published/index.json",
      "published_artifacts_readme": "benchmarks/published/README.md",
      "sources": [
        "docs/CONTRIBUTOR.md"
      ]
    }
  }
}
```

## Drift Rule

If any command, path, or source in this file changes, the corresponding source documents and implementation entrypoints must be updated in the same change unless the user explicitly directs otherwise.
