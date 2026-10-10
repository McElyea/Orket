# Orket 0.8.0: Apache-2.0 cutover

Date: 2026-10-10
Status: Release contract; publication is identified by the matching core/SDK tags and release assets

Orket original code, SDK, documentation, examples, and templates move to
Apache-2.0. Commercial use, hosting, and embedding are permitted under its terms
without the former employee-count or competitive-offering restrictions.

The user explicitly selected 0.8.0 across core, SDK, extension templates and
manifests, companion frontend, TypeScript conformance package, and private root
npm package. This is a licensing/package boundary. It introduces no new runtime
API, wire schema, provider guarantee, or platform-support claim.

## Ownership and third-party scope

On 2026-10-10 the owner confirmed control of Orket original code and no known
employer/client, outside-contributor, or signed-agreement restriction preventing
Apache licensing. The locally available Git history showed one author identity;
that observation does not independently establish legal title.

The bundled companion frontend includes React, Radix, Lucide, helper packages,
and seven font families. Their MIT/ISC/OFL terms and original notices remain.
Upstream license texts were collected from lockfile-integrity-verified npm
archives. Radix packages lacking a packaged LICENSE use the upstream LICENSE at
the exact `gitHead` published for that package version. All 28 bundled WOFF/WOFF2
files matched the locked upstream package bytes. The notice inventory includes
all locked production dependencies conservatively and the Vite core MIT helper.

The root `LICENSE` is the unchanged official Apache-2.0 text (SHA-256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`).
The root `NOTICE` retains Orket attribution. The SDK and templates receive checked
copies; `THIRD_PARTY_NOTICES.txt` accompanies the core and companion assets.

Earlier releases, published bytes, Git tags, and BSL change-date commitments are
preserved. This change does not amend an existing signed agreement or grant new
terms to historical artifacts.

## Compatibility and operator action

- `compatibility_status`: `preserved`
- `affected_audience`: `all`
- `migration_requirement`: `none`

No application source or stored-state migration is required for this licensing
change. Install core and SDK 0.8.0 together to adopt the new release family.
Newly generated templates use that same SDK. Older generated projects and
historical compatibility evidence retain their original scope.

The deprecated `python main.py` wrapper and hidden `--rock` alias remain
supported through 0.8.x; their removal still requires a separate accepted change.

## Stability and evidence

Runtime behavior is unchanged. Fresh Windows proof covers installed CLI startup,
HTTP health, package isolation, frontend rebuilding and an actual llama.cpp
workflow with six measured model calls and verified replay. The CLI retains its
existing degraded-startup warning. The 301 selected release tests passed.

Earlier Windows coverage (13,252 passed, 93 skipped, 89.25%) is retained only after
auditing unchanged runtime bytes; this is not a fresh full-suite measurement.
Verification scope and observed failures are recorded in [PROOF_REPORT.md](PROOF_REPORT.md).
The version number alone does not establish full runtime, Mac, or hosted-CI
acceptance. Licensing authority: `docs/specs/LICENSING_POLICY.md`.
