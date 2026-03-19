# CURRENT_AUTHORITY.md

Last updated: 2026-03-19

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
10. Staged artifact candidate index: `benchmarks/staging/index.json`
11. Published artifact index: `benchmarks/published/index.json`
12. Canonical provider runtime target selection: `orket/runtime/provider_runtime_target.py`
13. Core release/versioning policy: `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
14. Core release gate checklist: `docs/specs/CORE_RELEASE_GATE_CHECKLIST.md`
15. Core release proof report template: `docs/specs/CORE_RELEASE_PROOF_REPORT.md`
16. Core release proof report storage: `docs/releases/<version>/PROOF_REPORT.md`
17. Core release evidence storage: `benchmarks/results/releases/<version>/`
18. Core release automation workflow: `.gitea/workflows/core-release-policy.yml`
19. Core release automation script: `scripts/governance/check_core_release_policy.py`
20. Core release prep script for release-only worktrees: `scripts/governance/prepare_core_release.py`
21. Canonical core release tag rule: every post-`0.4.0` versioned commit on pushed `main` must carry the matching annotated `v<major>.<minor>.<patch>` tag on that exact commit.
22. Pytest sandbox fail-closed fixture: `tests/conftest.py`
23. Determinism claim/gate policy: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Machine-Readable Authority Map (v1)

```json
{
  "version": 1,
  "last_updated": "2026-03-19",
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
      "pytest_sandbox_default_policy": "tests/conftest.py",
      "sources": [
        "AGENTS.md",
        "docs/CONTRIBUTOR.md",
        "docs/TESTING_POLICY.md",
        "tests/conftest.py"
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
        "docs/specs/TOOL_CONTRACT_TEMPLATE.md",
        "docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_REPAIR_LEDGER_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_ARTIFACT_PROVENANCE_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_NARRATION_EFFECT_AUDIT_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_SOURCE_ATTRIBUTION_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_MEMORY_TRUST_CONTRACT.md",
        "docs/specs/TRUTHFUL_RUNTIME_CONFORMANCE_GOVERNANCE_CONTRACT.md"
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
      "determinism_gate_policy_source": "docs/specs/ORKET_DETERMINISM_GATE_POLICY.md",
      "local_prompting_contract_source": "docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md",
      "sources": [
        "docs/README.md",
        "docs/ROADMAP.md",
        "docs/CONTRIBUTOR.md"
      ]
    },
    "canonical_script_output_locations": {
      "staged_artifacts_index": "benchmarks/staging/index.json",
      "staged_artifacts_readme": "benchmarks/staging/README.md",
      "published_artifacts_index": "benchmarks/published/index.json",
      "published_artifacts_readme": "benchmarks/published/README.md",
      "artifact_review_policy": "docs/process/PUBLISHED_ARTIFACTS_POLICY.md",
      "sources": [
        "docs/CONTRIBUTOR.md",
        "docs/process/PUBLISHED_ARTIFACTS_POLICY.md"
      ]
    },
    "core_release_versioning": {
      "primary": "docs/specs/CORE_RELEASE_VERSIONING_POLICY.md",
      "release_gate_checklist": "docs/specs/CORE_RELEASE_GATE_CHECKLIST.md",
      "release_proof_template": "docs/specs/CORE_RELEASE_PROOF_REPORT.md",
      "release_proof_reports_root": "docs/releases/",
      "release_evidence_root": "benchmarks/results/releases/",
      "automation_workflow": ".gitea/workflows/core-release-policy.yml",
      "automation_script": "scripts/governance/check_core_release_policy.py",
      "release_prep_script": "scripts/governance/prepare_core_release.py",
      "main_commit_tags_required": true,
      "tag_format": "v<major>.<minor>.<patch>",
      "core_version_source": "pyproject.toml",
      "changelog_source": "CHANGELOG.md",
      "workflow_source": "docs/CONTRIBUTOR.md",
      "sdk_versioning_source": "docs/requirements/sdk/VERSIONING.md",
      "sources": [
        "CURRENT_AUTHORITY.md",
        ".gitea/workflows/core-release-policy.yml",
        "scripts/governance/check_core_release_policy.py",
        "scripts/governance/prepare_core_release.py",
        "docs/specs/CORE_RELEASE_VERSIONING_POLICY.md",
        "docs/specs/CORE_RELEASE_GATE_CHECKLIST.md",
        "docs/specs/CORE_RELEASE_PROOF_REPORT.md",
        "docs/CONTRIBUTOR.md",
        "CHANGELOG.md",
        "pyproject.toml"
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
