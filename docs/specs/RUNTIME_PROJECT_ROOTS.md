# Runtime project roots

Status: Active contract; scoped BT-5 project-root proof accepted
Last updated: 2026-09-17
Owner: Orket Core

## Project selection

The default operator project is the process working directory at invocation.
`orket/project_paths.py` owns this default for discovery, the driver and structural
reconciliation. It must not infer mutable project state from the installed
package location. Explicit project roots retain their existing precedence.

`ConfigLoader` accepts a project root and resolves its `config/` and `model/`
children. Discovery and the driver must pass that project root, not its `model/` child. The
standard card engine resolves the same default project through its existing
config-root bootstrap. No second loader or package-directory fallback is admitted.

For project root `P`:

| Consumer | Selected root |
|---|---|
| Default driver project and filesystem tools | `P` |
| Discovery and driver `ConfigLoader` | `P`, with its existing config/model precedence |
| Structural reconciler board | `P/model` |
| Default driver/reconciler workspace | `P/workspace/default` |
| Card execution config root | Existing explicit override, otherwise invocation project `P` |
| Card execution workspace | Existing explicit `--workspace`/application input |

Changing the execution workspace does not implicitly select another project or
move board assets. API-owned roots remain explicit and instance-owned. Existing
objects that capture a project root retain it; concurrent process-wide working
directory changes during invocation are not supported.

Package-owned contracts, schemas, registries and the governed-run demo retain
their existing packaged-asset authority. They do not become caller-owned defaults
through this change. Model weights, provider selection and provider fallback
policy are unchanged.

`orket ext init` likewise reads packaged extension-template archives, independently
of the caller's directory or a neighboring source checkout. Application scaffold
authority validates the selected kind and target intent; the storage worker reads,
contains and verifies materialized files before reporting success. Existing targets
require `--force`. This is per-file verified publication, not an atomic directory
transaction or OS fencing against concurrent external editors. Source/archive
maintenance follows `docs/CONTRIBUTOR.md`.

## Migration and failure

No project files are moved, merged, copied, initialized or deleted by root
selection. Operators who previously relied on package-relative project discovery
must run from their intended project or supply the existing explicit root input.
An absent/inaccessible board still produces the existing truthful reconciliation
failure; choosing a caller root does not fabricate a successful empty board.
Actual reconciliation retains its existing effects and startup ordering.

Runtime database selection follows `docs/specs/RUNTIME_STORE_BINDING.md`: resolve
the runtime path once against the invocation directory and use its sibling
control-plane store. Historical relative epic scopes require explicit offline
migration. Project-root selection itself neither moves stores nor authorizes
merging history; storage migration has its own copied-history/restart proof.

## Acceptance

Use real staged project files through discovery and structural reconciliation,
including two distinct invocation roots, a driver retaining its captured root,
explicit-root precedence, missing-board failure and installed execution outside
the checkout. Confirm the package tree remains unchanged. Repeat successful and
unsuccessful stock llama.cpp card flows against the rebuilt installed candidate;
startup, manifest assets, execution outcome and retained evidence must agree.
Preserve the accepted A/B and BT-1 through BT-4 guarantees.
