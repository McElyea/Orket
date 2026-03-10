# CURRENT_AUTHORITY.md

Last updated: 2026-03-10

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
9. Long-lived specs root: `docs/specs/`
10. Published artifact index: `benchmarks/published/index.json`
11. Canonical provider runtime target selection: `orket/runtime/provider_runtime_target.py`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-03-10",
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
      "specs_root": "docs/specs/",
      "active_roadmap_source": "docs/ROADMAP.md",
      "process_source": "docs/CONTRIBUTOR.md",
      "core_runtime_contract_sources": [
        "docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md",
        "docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md",
        "docs/specs/RUNTIME_INVARIANTS.md",
        "docs/specs/TOOL_CONTRACT_TEMPLATE.md"
      ],
      "offline_capability_matrix_source": "docs/specs/OFFLINE_CAPABILITY_MATRIX.md",
      "protocol_governed_contract_sources": [
        "docs/specs/PROTOCOL_GOVERNED_RUNTIME_CONTRACT.md",
        "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
        "docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md",
        "docs/specs/PROTOCOL_ERROR_CODE_REGISTRY.md",
        "docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md",
        "docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md"
      ],
      "operating_principles_source": "docs/specs/ORKET_OPERATING_PRINCIPLES.md",
      "local_prompting_contract_source": "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
      "sources": [
        "docs/README.md",
        "docs/ROADMAP.md",
        "docs/CONTRIBUTOR.md"
      ]
    },
    "canonical_script_output_locations": {
      "published_artifacts_index": "benchmarks/published/index.json",
      "published_artifacts_readme": "benchmarks/published/README.md",
      "sources": [
        "docs/CONTRIBUTOR.md"
      ]
    },
    "model_provider_runtime_selection": {
      "primary": "orket/runtime/provider_runtime_target.py",
      "runtime_consumers": [
        "orket/adapters/llm/local_model_provider.py",
        "orket/workloads/model_stream_v1.py"
      ],
      "verification_consumers": [
        "scripts/providers/check_model_provider_preflight.py",
        "scripts/providers/list_real_provider_models.py"
      ],
      "sources": [
        "CURRENT_AUTHORITY.md",
        "docs/CONTRIBUTOR.md",
        "scripts/README.md"
      ]
    }
  }
}
```

## Drift Rule

If any command, path, or source in this file changes, the corresponding source documents and implementation entrypoints must be updated in the same change unless the user explicitly directs otherwise.
