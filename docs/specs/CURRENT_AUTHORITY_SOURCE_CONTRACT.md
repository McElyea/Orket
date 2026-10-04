# Current authority source contract

Status: Active
Owner: Orket Core
Last updated: 2026-10-03

## One bounded current index

`docs/architecture/current_authority.json` is the authored index.
`CURRENT_AUTHORITY.md` is its deterministic generated view. Existing implementation,
contracts, CONTRIBUTOR, the dependency policy and governed start-path matrix retain
their authority. The index routes readers to them and does not copy their rules.

The manifest is UTF-8 without BOM, at most 32 KiB and 40 current records. Its closed
record kinds are commands, canonical references, active contracts, ownership,
compatibility, claim ceilings and proof availability. Stable IDs identify current
scopes; replacing an observation must not append a release history. Unknown fields,
duplicate JSON keys/IDs/scopes, missing required sections or canonical command and
reference inventories, nonfinite values, future/invalid dates and overflow refuse.
The generated view is bounded to 32 KiB and 160 lines; overflow never truncates.

Preserve the complete final pre-cutover `CURRENT_AUTHORITY.md` bytes at
`docs/architecture/history/CURRENT_AUTHORITY_PRE_MANIFEST_2026-09-28.md`. Bind their
SHA-256 in the manifest at application time. The historical copy remains tracked
and linked, but cannot grant current acceptance. Current obligations retain their
existing canonical contracts, the active remediation plan and exception register.
An exact historical copy does not excuse dropping a current obligation's owner.

## Source and command checks

The checker uses the existing Git-visible inventory, including nonignored untracked
files. Source paths must remain inside the selected repository; ignored/missing
inputs, failed Git discovery, changed observations, missing Python declarations and
ambiguous/inactive spec headers refuse. `contract` and `owners` records require one
opening `Status: Active...` declaration. The index and generated view cannot supply
their own source support. Canonical indexes retain their existing status conventions;
their inclusion does not promote every document they mention to an active contract.

Command argv must exactly match a Markdown code declaration or an actual YAML job
`run` line from its named canonical source. Comments, echoed commands and compound
shell commands are not accepted declarations. The checker derives script/module
paths from argv, verifies a declared `main` and native `__main__` invocation, or
follows the actual `[project.scripts]` console binding to its declared callable.
An authored pointer cannot substitute for a missing executable target. Development
tools bind to package dependency declarations; the editable install binds both
core and SDK extras. These observations do not execute a parser, install, workload,
provider, server or CI job. Argument values and runtime prerequisites remain owned
by their real parsers and contracts. Exact documentation parity is not acceptance.

Ownership records observe declared implementation symbols and link the governing
contract. They do not infer transitive call behavior, natural-language equivalence,
or runtime compliance. Duplicate typed scopes refuse instead of resolving conflicts
by order. Claim-ceiling postures have a closed vocabulary; arbitrary product support
or trust levels cannot be introduced by a new string.

## Compatibility and proof limits

Compatibility conditions must occur in the canonical source. A supplied calendar
expiry must be a valid declared date and remain in the future; reaching that date
requires an explicit disposition. Condition-bound removals have no invented calendar
deadline. An unassigned version window remains visible debt rather than an inferred
permission to remove an alias. The 0.7.0 release explicitly preserves the source
wrapper through 0.7.x; its later removal requires a separate accepted contract
delta and installed-root proof. This checker does not infer a release from prose.

Proof is `unavailable` or `historical`. Historical rows require a nonfuture ISO date;
unavailable rows cannot carry an observation date. Neither grants current proof.
All current-proof states and `--require-current-proof` requests refuse because no
portable runtime-evidence adapter is implemented. The current plan retains scoped
results and their limits; this index does not certify receipt origin or freshness.
Any future portable adapter requires a reviewed contract and adverse controls.

## Native tooling

- Generate: `python scripts/governance/render_current_authority.py`.
- Compare without writing: `python scripts/governance/render_current_authority.py --check`.
- Validate: `python scripts/governance/check_current_authority.py`.
- Explicit unavailable-proof control: `python scripts/governance/check_current_authority.py --require-current-proof`.

Both tools share one validation path and the pure renderer. The checker reports
`structural_authority_valid`, `current_proof_established` and
`requested_proof_satisfied` separately. Without a proof request, structural success
does not establish current proof. Its single stable report is
`benchmarks/results/governance/current_authority_check.json`, using the shared
rerun diff ledger. Incomplete source admission leaves the prior report untouched;
generated-view mismatch and unavailable-proof requests produce explicit failed
reports after complete admission. Output aliases and unrelated existing destinations
refuse. Input/output checks are cooperative native observations, not hostile race
isolation. Failed publication can leave a partial output; rerender/check must pass
before claiming a usable view.

The structural contract controls and native Git/filesystem/CLI tests are separate
from runtime parity, coverage, hosted Quality and the ordered E2 decomposition.
