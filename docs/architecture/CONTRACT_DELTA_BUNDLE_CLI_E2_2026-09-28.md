# Bundle CLI interface decomposition

## Summary
- Owner: Orket Core.
- Date: 2026-09-28.
- Status: implemented; scoped source and Windows installed parity pass.
- Public arguments, result formats, entrypoints and application authority remain
  unchanged. This records internal ownership and private-consumer migration.

## Delta

The 1,017-line `orket/interfaces/orket_bundle_cli.py` becomes 262 lines and keeps
`main`, `validate_sdk_extension` and `validate_external_extension`. Four modules
own cohesive interface work:

- `bundle_cli_arguments.py`: ordered parser declarations, 322 lines.
- `bundle_cli_output.py`: human rendering and ordinary result emission, 131 lines.
- `bundle_review_cli.py`: review preparation, dispatch and error projection,
  143 lines.
- `bundle_outward_cli.py`: existing run, approval, ledger and connector handlers,
  220 lines.

New functions remain within 70 lines. The installed `orket -> orket.cli:main`
entrypoint and bundle module entrypoint retain their distinct runtime behavior.
Review scope-conflict output remains before its execution catch; replay argument
error output remains inside it. Exception-handler output and successful output
remain outside that catch. Bounds, policy/workspace resolution and service
construction keep their original failure propagation. HTTP admission, deadlines,
result projections and application service arguments do not change.

## Migration and rollback

Private parser, review and HTTP helpers have no compatibility exports. The four
affected repository test consumers patch their actual service/module owners;
all original assertions and case identities remain. Third-party imports of these
private helpers have not been verified. No proxy, duplicated renderer, new policy
owner or transport migration is introduced.

Rollback must restore the root and its four consumer migrations together, remove
the four extracted modules, and preserve the public output-boundary regressions
and before evidence. There is no data migration or compensation operation.

## Verification and limits

The unchanged product passes all 113 cases in the 24-selector source selection.
The 13 new contract cases exercise public-main parsing/printing with a supplied
review service and failing output sink; they do not prove a live review backend.
The actual parser baseline records 45 parse vectors, eight public-main cases and
recursive help/action declarations. The six-command CLI smoke passes scaffold,
API dry-run/apply/no-op and refactor dry-run/apply with real temporary Git/files
and a declared successful verification-command fixture. Temporary workspaces are
removed. All 5,521 Git-visible inputs remain unchanged during each before run.

Closing source execution passes the same 113 cases in 28.33 seconds, with all
5,526 inputs unchanged. All 45 parse vectors, eight public-main cases and 63
recursive parser nodes match exactly. All six actual smoke results match after
normalizing only the separately created, subsequently removed scaffold directory.
Raw reports retain both paths. Canonical Ruff and dependency direction pass.

Structural extraction comparison retains the parser's 207 calls/145 argument
declarations, human-render AST, 18 moved/retained functions, 28 application or
transport call argument lists and 43 consumer definitions after explicit owner
renaming. These are structural observations alongside the executed controls.

Source before evidence lives under `.tmp/goal-20260928-bundle-before-v1-*` and
`.tmp/e2-bundle-cli-candidate-20260928/`. Fresh before/after wheel acceptance is
scoped to Windows Python 3.11.14. Each fresh wheel passes 24 actual console/module
checks and three native bundle/demo/offline-ledger cases from a package-free
harness. Raw CLI stdout/stderr hashes and exits match exactly; all child processes
are reaped. Installed origins and namespace bytes remain bound to their wheels;
the only five namespace changes are the reviewed CLI modules. Before/after
readbacks live in `.tmp/e2-bundle-cli-campaign-20260928/{before,after}/readback.json`.

The console runtime-help case emits its pre-existing structural reconciliation
warning in both installed runs: that subpath is degraded despite exit zero.
Help parity does not establish healthy runtime reconciliation. Earlier frozen
wheels do not certify this extraction. Broader async ownership, Python 3.12/Linux,
provider, hosted Quality and full coverage obligations remain.

## Versioning

Dirty candidate after 0.6.114; no version, commit or tag change. The next retained
commit follows the existing release policy. This extraction grants no additional
workload, provider, effect or completion authority.
