# Dependency policy v2 cutover

Owner: Orket Core
Date: 2026-09-14
Status: Implementation in progress; repository conformance not yet accepted

The policy at `model/core/contracts/dependency_direction_policy.json` replaces its
v1 denylist and legacy-edge budget with allowed edges among the five normative
layers. The architecture remains the rule authority; the policy encodes its
classifications, permitted edges, exact decision-node contract/adapter targets and
individually governed exceptions. Extra platform/runtime/legacy layer labels no
longer exempt dependencies. Classification describes ownership, not proof of core
purity; D must resolve effects and implicit inputs inside modules classified core.

The checker and graph exporter share Git-visible discovery and Python-encoding-aware
import analysis. Relative imports, module/member imports and recognized dynamic
import forms participate in the graph. Unresolved import/reflection observations,
read/parse/discovery errors, unknown classification, forbidden edges and cross-layer
strongly connected components prevent acceptance. The observed graph and policy
verdict are separate report fields. Conservative static evidence does not establish
hostile-code containment or a runtime call graph.

Each exception names one exact source/target module pair, owner, reason,
introduction date and removal condition, with optional expiry. Exceptions cannot
waive analysis errors or authority cycles. Consumption and stale exceptions are
reported separately. This cutover introduces no blanket exceptions; existing
violations remain failures until repaired or individually reviewed.

The canonical command is `python scripts/governance/check_dependency_direction.py`.
The v1 `--legacy-edge-enforcement` and `--legacy-edge-max` options retire in the
same change as their callers; no silent compatibility mode remains. Report schema
v2 is an intentional governance-tool boundary change. Core runtime/package APIs
are unchanged and no release/version/tag action is performed by this cutover.

Migration updates the two `.gitea` Quality invocations first, then their contract
tests and downstream baseline/export consumers. Validation requires adversarial
fixture repositories, actual native checker/export commands, retained source input
hashes and a disclosed repository verdict. A red repository verdict is not a failed
collection or permission to weaken the policy. C acceptance requires every current
edge to conform or have an exact governed disposition.

If analysis defects prevent truthful reporting, repair against retained positive
and negative fixtures before accepting C. Reverting the implementation would also
require reverting its workflow/report consumers and restoring an explicit v1
transition-only status; a v1 green must never be presented as v2 conformance. No
runtime state migration or deletion is part of this change.
