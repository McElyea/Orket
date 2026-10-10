# Release 0.8.0 proof report

Date: 2026-10-10 (America/Denver)
Owner: Orket Core
Git tags: `v0.8.0` and `sdk-v0.8.0`, required on the same release commit
Status: Windows release gates accepted; remote refs and publication asset attest publication
Release authority: [policy](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md),
[checklist](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)
Authorized boundary: Apache-2.0 cutover; no unrelated roadmap project is closed

## What changed

Orket original work uses the unchanged official Apache-2.0 text. Core, SDK,
both template packages/manifests, companion frontend, conformance package and
private root npm package use 0.8.0. Core and templates require SDK 0.8.0.
Full MIT/ISC/OFL notices remain with bundled frontend code and fonts. License
copies, wheel/sdist metadata and nested template notices have mechanical guards.
Historical releases and BSL commitments remain intact.

Runtime APIs, wire schemas and stored state are unchanged. Deprecated main.py
and rock aliases remain supported through 0.8.x. The valid bundle test fixture
now admits 0.8.0; explicit historical bounds still reject excluded versions.
Licensing contract: [LICENSING_POLICY.md](docs/specs/LICENSING_POLICY.md).

## Stability and compatibility

Acceptance is scoped to native Windows, Python 3.11.14. Installed CLI, HTTP health,
package isolation, quickstart, local API/storage cleanup and actual llama.cpp
workflow observations pass. The CLI retains its existing degraded-startup warning.

- `compatibility_status`: `preserved`
- `affected_audience`: `all`
- `migration_requirement`: `none`

Install core and SDK 0.8.0 together. No application source or stored-state migration
is required. This version alignment does not admit other core/SDK pairings or
platforms. The active Mac lane remains open.

## What was verified

Proof is live native execution plus separately identified structural/contract
checks. Overall observed result: **success**. Installed CLI path: **degraded**;
other successful surfaces: **primary**. All evidence below is under
`benchmarks/results/releases/0.8.0/` and included in the release evidence archive.

| Surface name | Surface type | Proof mode | Proof result | Reason / observed path | Evidence |
| --- | --- | --- | --- | --- | --- |
| Installed `orket runtime` | default_runtime_entrypoint | live | success | Existing startup warning / degraded | `release-installed.json`, `release-artifacts.json` |
| Canonical `python server.py`, real HTTP health | api_runtime_entrypoint | live | success | HTTP 200 with expected body; native cleanup and closed port / primary | `release-installed.json` |
| Governed-action quickstart approve/deny | workflow_path | live | success | Actual file/ledger effects; fresh verification and tamper refusal / primary | `verification.json` |
| Installed local-agent workflow on llama.cpp | integration_route | live | success | Six measured model calls, accepted durable result, fresh inspect/replay / primary | `release-installed.json` |
| Core/SDK packaging, SDK-only install and templates | integration_route | live | success | Fresh external installs and byte/namespace inspection / primary | `verification.json`, `release-installed.json`, `release-artifacts.json` |
| Installed API/auth/storage and webhook lifetime | integration_route | live | success | Local ASGI/SQLite and signature/cleanup controls / primary | `verification.json`, 16 installed tests |

**Default runtime:** the installed console command starts the interactive driver,
accepts `quit`, exits zero and settles under native Windows Job ownership. The
final rebuilt candidate repeats this path and reports SDK 0.8.0. No model call
is inferred from interactive startup alone.

**API:** only the canonical source launcher is copied to a private directory;
runtime imports come from the installed wheel. Actual HTTP returns 200 and
`{"status":"ok"}`. The health-only server is cancelled through its native owner,
with complete capture and closed port. This is not graceful server-shutdown proof;
the separate 16 installed controls establish their bounded application cleanup.

**Actual provider workflow:** guided setup and `orket demo local-agent` use the
existing operator-owned llama.cpp b11146 server and the selected Qwen3.8 GGUF.
Six returned, measured calls consumed 754 input and 378 output tokens with no
repair calls. Two iterations produced open=2, closed=2, blocked=1 with expected
artifact references and accepted final truth. Fresh-process inspection/replay
matched without changing the database. Server identity/model/template evidence
is retained; the borrowed server stayed running. Remote model termination and
ownership of that server are not claimed.

**Distribution proof:** the initial campaign passed 32 commands, including eight
wheel/sdist inspections across core, SDK and both generated templates, 16 installed
tests, and an actual Vite rebuild retaining full notices. All 31 non-HTML static
files matched; index.html differed only in newline encoding. The closeout passed
15 commands and 234 tests (overlapping the later release selection).

Fresh release selection: **301 passed**, one existing TestClient deprecation
warning. Canonical Ruff, Mypy (1,232 files), dependency enforcement, strict taxonomy
(13,370 items) and critical no-op checks passed. These are structural/contract
gates, not independent runtime proof. Source release checks used six settled
commands; installed release acceptance used 14 plus the owned HTTP server.

Final SDK README release wording required fresh artifacts. The final campaign
builds from another clean snapshot, independently installs the matched wheels,
checks origins and licenses, then compares namespaces with the accepted candidates.
All 1,250 other core files and all 31 SDK files match exactly. The default template
archive differs only by removal of a surplus EOF newline in its two third-party
notice copies, confirmed by examining every nested member. Fresh installed
scaffold generation, strict validation and license/scaffold controls pass.
Runtime Python bytes are identical to the accepted candidate.
Final artifact identities appear below and in `assets/SHA256SUMS-0.8.0.txt`.

**Retained coverage:** the earlier 0.7.8 Windows run passed 13,252 tests with 93
skips, three pytest warnings and 89.25% coverage at the unchanged 89% floor.
`baseline/audit.json` independently verifies its receipt/log/measurement hashes,
unchanged coverage/pytest configuration and all 1,231 core Python files. Only
the two template archives differ in the core namespace; the SDK's only Python
change is its version. This is structural relevance evidence for an earlier live
run, not a new 0.8.0 full-suite measurement or whole-environment identity claim.
The retained incomplete worker coverage file remains disclosed in that audit.

## Failure accounting

The initial release bundle selection was 26 passed / 3 failed because the valid
fixture excluded 0.8.0. The fixture and contract expectations were corrected;
the later 301-test run passed while preserving historical rejection. Initial
JUnit remains `bundle-initial.xml`.

The first HTTP probe attempt encountered ConnectTimeout during startup. Its
server had reached readiness and was fully settled. The private probe now uses
the existing finite 45-second readiness loop for all transport errors, matching
the repository's established probe. The succeeding run observed HTTP 200.
The failed receipt/logs are retained; no runtime assertion or deadline changed.

The initial isolated harness also emitted seven unknown-marker registration
warnings because it omitted repository marker declarations. All 16 selected
tests ran; no warning or failure is presented as absent.

The first staged whitespace check found an extra EOF blank line in the aggregate
third-party notices. Publication stopped before committing. Canonical/copy text
and the template archive were synchronized, fresh artifacts were built, and the
scoped notice/scaffold controls and staged whitespace check were rerun. Earlier
candidate assets remain retained as superseded local evidence.

## What was not verified

No fresh full-suite coverage, hosted Gitea execution, native Mac/Metal, alternate
Python/platform matrix, live Docker sandbox acceptance, production soak or new
provider/model support is claimed. Earlier evidence retains its original scope.
Owner confirmation represents ownership; it is not an independent title audit.

## Remaining blockers or drift

Orket Core records checklist-backed acceptance for this bounded Windows minor
release under the user's explicit instruction to merge and cut the release.
The licensing exception authorizes the version boundary; it does not waive proof
or close the Mac/architectural-truth umbrella. No unresolved license-copy,
package-version, artifact-metadata or template-notice drift was observed.

AC-01 through AC-10 pass for this increment: no runtime dependency edges,
decision nodes, inputs, effects, adapters, events or replay behavior changed.
The existing architecture exceptions are not widened. Version/license and
compatibility authority changed together. Broader conformance remains separate.

Publication requires final source checks, a commit on main, matching annotated
tags, atomic branch/tag push, remote peeled-identity readback, GitHub releases,
and downloaded-asset byte comparison. `publication.json` is the independent
publication witness. No PyPI or npm registry publication is claimed.

## Final artifacts

- `orket-0.8.0-py3-none-any.whl`: `adaba37462fd1c52046dc4f53beb569b9ecf234b48876a47b61b10ba4bceaff7`
- `orket-0.8.0.tar.gz`: `1d761d7c70579b744447a7de3fcfc0eb7ac3f10b35a2e30b3200edef9097da8c`
- `orket_extension_sdk-0.8.0-py3-none-any.whl`: `4ad1b2732a502ae4544335bf8a7419a6b951e60477dad92d06df90050993ca51`
- `orket_extension_sdk-0.8.0.tar.gz`: `511faeab675a1fae707f256d62251c2854b6f52c79913871bccbbf3199b243f9`

## Exact files touched

Authored/generated repository changes follow. Ignored evidence, external
installations and local editable metadata are verification outputs.

- [.gitea/workflows/quality.yml](.gitea/workflows/quality.yml)
- [.gitea/workflows/sdk-package-release.yml](.gitea/workflows/sdk-package-release.yml)
- [CHANGELOG.md](CHANGELOG.md)
- [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)
- [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)
- [LICENSE](LICENSE)
- [NOTICE](NOTICE)
- [README.md](README.md)
- [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)
- [conformance/ts/package.json](conformance/ts/package.json)
- [docs/CONTRIBUTOR.md](docs/CONTRIBUTOR.md)
- [docs/README.md](docs/README.md)
- [docs/RUNBOOK.md](docs/RUNBOOK.md)
- [docs/architecture/CONTRACT_DELTA_APACHE_CUTOVER_2026-10-10.md](docs/architecture/CONTRACT_DELTA_APACHE_CUTOVER_2026-10-10.md)
- [docs/architecture/current_authority.json](docs/architecture/current_authority.json)
- [docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json](docs/projects/architectural-truth/ARCHITECTURE_EXCEPTION_REGISTER.json)
- [docs/releases/0.8.0/PROOF_REPORT.md](docs/releases/0.8.0/PROOF_REPORT.md)
- [docs/releases/0.8.0/RELEASE_NOTES.md](docs/releases/0.8.0/RELEASE_NOTES.md)
- [docs/requirements/sdk/VERSIONING.md](docs/requirements/sdk/VERSIONING.md)
- [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)
- [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
- [docs/specs/CURRENT_AUTHORITY_SOURCE_CONTRACT.md](docs/specs/CURRENT_AUTHORITY_SOURCE_CONTRACT.md)
- [docs/specs/LICENSING_POLICY.md](docs/specs/LICENSING_POLICY.md)
- [docs/templates/external_extension/LICENSE](docs/templates/external_extension/LICENSE)
- [docs/templates/external_extension/NOTICE](docs/templates/external_extension/NOTICE)
- [docs/templates/external_extension/extension.yaml](docs/templates/external_extension/extension.yaml)
- [docs/templates/external_extension/pyproject.toml](docs/templates/external_extension/pyproject.toml)
- [docs/templates/external_extension/src/companion_app/frontend/package-lock.json](docs/templates/external_extension/src/companion_app/frontend/package-lock.json)
- [docs/templates/external_extension/src/companion_app/frontend/package.json](docs/templates/external_extension/src/companion_app/frontend/package.json)
- [docs/templates/external_extension/src/companion_app/frontend/public/THIRD_PARTY_NOTICES.txt](docs/templates/external_extension/src/companion_app/frontend/public/THIRD_PARTY_NOTICES.txt)
- [docs/templates/external_extension/src/companion_app/static/THIRD_PARTY_NOTICES.txt](docs/templates/external_extension/src/companion_app/static/THIRD_PARTY_NOTICES.txt)
- [docs/templates/governed_agent_external/LICENSE](docs/templates/governed_agent_external/LICENSE)
- [docs/templates/governed_agent_external/NOTICE](docs/templates/governed_agent_external/NOTICE)
- [docs/templates/governed_agent_external/extension.yaml](docs/templates/governed_agent_external/extension.yaml)
- [docs/templates/governed_agent_external/pyproject.toml](docs/templates/governed_agent_external/pyproject.toml)
- [orket/runtime/config/assets/extension_templates/external_extension.zip](orket/runtime/config/assets/extension_templates/external_extension.zip)
- [orket/runtime/config/assets/extension_templates/governed_agent_external.zip](orket/runtime/config/assets/extension_templates/governed_agent_external.zip)
- [orket_extension_sdk/CHANGELOG.md](orket_extension_sdk/CHANGELOG.md)
- [orket_extension_sdk/LICENSE](orket_extension_sdk/LICENSE)
- [orket_extension_sdk/NOTICE](orket_extension_sdk/NOTICE)
- [orket_extension_sdk/README.md](orket_extension_sdk/README.md)
- [orket_extension_sdk/__version__.py](orket_extension_sdk/__version__.py)
- [orket_extension_sdk/pyproject.toml](orket_extension_sdk/pyproject.toml)
- [package.json](package.json)
- [pyproject.toml](pyproject.toml)
- [scripts/ci/candidate_install_support.py](scripts/ci/candidate_install_support.py)
- [scripts/governance/check_licenses.py](scripts/governance/check_licenses.py)
- [scripts/sdk/check_sdk_tag_version.py](scripts/sdk/check_sdk_tag_version.py)
- [tests/core/test_orket_manifest_contract.py](tests/core/test_orket_manifest_contract.py)
- [tests/fixtures/orket_manifest/valid_minimal.json](tests/fixtures/orket_manifest/valid_minimal.json)
- [tests/integration/test_candidate_install_evidence.py](tests/integration/test_candidate_install_evidence.py)
- [tests/integration/test_distribution_licenses.py](tests/integration/test_distribution_licenses.py)
