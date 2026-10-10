# Licensing and distribution notices

Last updated: 2026-10-10
Status: Active
Owner: Orket Core

## Scope and authority

Orket original code, documentation, SDK, examples, and templates are licensed
under the unmodified Apache License, Version 2.0, starting with the coordinated
0.8.0 cutover. The repository-root `LICENSE` is the canonical license text;
`NOTICE` records Orket's copyright attribution. Apache's contribution, patent,
redistribution, disclaimer, and trademark terms apply as written.

Third-party components keep their own licenses. The root
`THIRD_PARTY_NOTICES.txt` is the canonical attribution inventory for bundled
companion frontend code and fonts. It includes the locked frontend production
dependencies conservatively, plus the MIT-licensed Vite core browser helper.
Build-only dependencies listed there are not claims that their code is shipped.
Independently installed Python/npm dependencies and optional model assets retain
their own terms; Orket's license does not relicense them.

The core and companion template distributions include Apache-2.0 original work
and MIT/ISC/OFL-1.1 third-party material. Their distribution expression is
`Apache-2.0 AND MIT AND ISC AND OFL-1.1`. The standalone SDK and governed-agent
starter use `Apache-2.0`. Package-level metadata describes the distributed
contents, while the root Apache text governs Orket original work.

Historical releases, tags, published bytes, and BSL change-date commitments
remain intact. The cutover does not rescind previously granted rights or amend
signed agreements. The owner confirmed control of Orket original work and no
known restrictions on 2026-10-10. That is an owner representation, not a legal
title determination produced by repository checks.

## Coordinated version boundary

The user explicitly selected 0.8.0 for core, SDK, both Python extension
templates and their extension manifests, companion frontend, TypeScript
conformance package, and private root npm package. Protocol and schema versions
continue to identify their existing contracts. Future SDK versions remain
independent under `docs/requirements/sdk/VERSIONING.md`.

This release retains the deprecated `python main.py` and hidden `--rock`
entrypoints through 0.8.x. Their removal still requires a separately accepted
contract delta and installed-path proof. The licensing version change does not
authorize runtime removals or claim new platform acceptance.

## Contribution terms

Contributions intentionally submitted for inclusion are offered under
Apache-2.0 as provided by section 5, unless explicitly stated otherwise and
accepted under a separate arrangement. Contributors must have authority to
submit the material and identify third-party sources and applicable notices.
Copyright remains with the applicable rights holder. Do not remove upstream
attribution or label third-party work as Orket original work.

## Distribution workflow

1. Edit the three canonical root license/notice files.
2. Run `python scripts/governance/check_licenses.py --write` to refresh the
   byte-identical SDK/template license copies and the companion public/static
   notice copies. Vite preserves the notice on future frontend builds by copying
   it from `frontend/public/` into `static/`.
3. Run `python scripts/governance/sync_extension_templates.py --write`, then
   `python scripts/governance/sync_extension_templates.py --check`.
4. Run `python scripts/governance/check_licenses.py` for source-copy agreement.
5. Build fresh wheel/sdist candidates without reused build or egg-info caches.
   Both distribution formats must contain the declared full license/notice texts.
6. Run `python scripts/governance/check_licenses.py --dist <core-dist-directory>`
   and `python scripts/governance/check_licenses.py --project orket_extension_sdk --dist <sdk-dist-directory>`.
   The checker compares actual metadata and notice bytes, rejects duplicate
   members, and checks notices inside the core's packaged extension archives.
7. Install the matched core/SDK candidates outside the checkout and run the
   affected installed commands. Preserve the existing release acceptance gates.

The candidate installer includes the root notices in its Git-visible snapshot
and applies the same wheel observer. Both Quality selections run source-copy
and adverse artifact controls; SDK release automation verifies its wheel and
sdist before smoke installation. Source/metadata checks are structural proof.
Native archive tests prove checker behavior, not legal ownership or runtime
acceptance. Hosted workflow definitions are not evidence of a hosted run.

When changing bundled dependencies or frontend assets, refresh the upstream
inventory and retain their complete applicable licenses before rebuilding the
template archive. Keep the original JavaScript license comments and font notices.
The 0.8.0 record identifies the upstream package versions and integrity checks.
