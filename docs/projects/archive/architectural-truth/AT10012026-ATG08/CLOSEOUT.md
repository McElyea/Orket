# ATG-08: Fresh Windows packages and public paths

Last updated: 2026-10-01 (America/Denver)
Status: Complete; v0.6.125 publication verified
Queue: ATG-v1 / ATG-08

## What changed

Built core 0.6.125 and SDK 0.7.0a1 sdists from a clean Git-visible snapshot, then
built wheels from those sdists. Installed those exact wheels into fresh external
Windows environments. No product, test, dependency or coverage configuration repair
was needed. The repository change contains version, release, queue and evidence
metadata, including the preceding v0.6.124 publication readback.

The build records base commit `1e5ce56f8cd864bfd75bdcb8230dd1ccfa63e8ce` separately
from the actual candidate bytes. Frozen prebuild version/docs changes are part of
that snapshot. Publication adds only the finite postproof metadata delta; it does
not claim that the preceding commit already contained the 0.6.125 snapshot.

## What was verified

Observed path: **primary**. Observed result: **success** for installed proof and
publication. Commit `b7ab34bba7d76a146cf4782c8522681de22ac544` and annotated tag
object `62dd5d79e43a67e5633a749534cfc0db8c445f79` were pushed atomically. Remote
branch/tag/peeled identities and a clean worktree verified at publication; later
ATG-09 metadata carries this readback. Main was not merged.

| Cell | Actual Python | Passed | Failed | Skipped | Pytest time |
|---|---|---:|---:|---:|---:|
| Windows py311 A01 | 3.11.14 | 6,231 | 0 | 3 | 1,637.60 seconds |
| Windows py312 A01 | 3.12.2 | 6,231 | 0 | 3 | 2,246.50 seconds |

Each run executes the same 6,234 source-bound cases selected by 467 selectors over
627 test files. There are no missing/extra cases, new skips or changed skip reasons.
The three skips are explicit owned-localhost-Gitea acceptance prerequisites.
Thirty-four checkout-only AST/declaration cases keep their separate ATG-07 source
proof; their exclusion does not become installed runtime proof.

Live controls exercise public CLI, API, governed demo/quickstart, file/SQLite/HTTP
effects and refusals, and native process/iterator/cleanup ownership. The selection
also contains contract and structural checks; the aggregate count does not classify
every case as live proof. Actual llama.cpp inference is not inferred from controlled
HTTP responses. Both runs use `ORKET_DISABLE_SANDBOX=1`.

Structural identity checks establish noneditable wheel installs outside the checkout,
successful `pip check`, exact source/sdist/wheel membership and bytes for 1,242 core
namespace members and 31 SDK members, and matching package versions. Neither product
namespace is copied into either harness. Parent imports and a separate isolated
origin child resolve to the installed environment. These checks do not independently
trace every runtime descendant import.

Both final receipts confirm unchanged installed namespaces, harness inputs and all
5,737 Git-visible candidate inputs. Final readback rechecks receipt/artifact hashes
and exact skip identities/reasons. Per-file outcomes, retained native properties,
the two warnings per interpreter, commands and artifact hashes are in
[VERIFICATION.json](VERIFICATION.json). Raw logs/artifacts live at the recorded
local paths and are not guaranteed to exist in another checkout.

The complete ATG-07 source gate remains distinct: 12,964 passed, zero failures,
93 skipped, and 89.213132% combined coverage against the unchanged 89% floor.
These installed selections are not a new complete coverage campaign.

Closeout structural validation passes: diff hygiene, project documentation hygiene,
authored/generated authority consistency and release policy, plus all 17 scoped
version/release tests. The validation receipt records unchanged inputs and the
exact postproof metadata delta; product, test and packaging inputs stay identical
to the installed candidate.

## What was not verified

Fresh Linux installed acceptance and current Linux host-clock reliability, the
three owned-localhost-Gitea cases, actual llama.cpp inference and hosted Gitea
Quality are not established here. General current-authority runtime proof remains
explicitly unavailable. Sandbox-disabled controls do not establish live Docker
acceptance. No main merge, whole-lane retirement or minor-release readiness is claimed.

## Remaining blockers or drift

ATG-09 still needs usable llama.cpp endpoint/model and hosted Gitea Quality access.
The earlier source API timing outlier remains unexplained; its unchanged assertion
passes on both installed cells. Grounding residue normalization and marshaller
process interruption/descendant ownership remain the queue's deferred findings.
The existing dependency warnings are retained in the receipt.

## Exact files touched

- `pyproject.toml`
- `CHANGELOG.md`
- `docs/projects/architectural-truth/ARCHITECTURAL_TRUTH_REMEDIATION_PLAN.md`
- `docs/projects/architectural-truth/GOAL_WORKSETS.json`
- `docs/projects/architectural-truth/README.md`
- `docs/projects/archive/architectural-truth/AT10012026-ATG07/CLOSEOUT.md`
- `docs/projects/archive/architectural-truth/AT10012026-ATG07/VERIFICATION.json`
- `docs/projects/archive/architectural-truth/AT10012026-ATG08/CLOSEOUT.md`
- `docs/projects/archive/architectural-truth/AT10012026-ATG08/VERIFICATION.json`
