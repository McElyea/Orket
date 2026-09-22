# Adapter effect classification

Last updated: 2026-09-22
Status: Implementation contract; acceptance belongs to the architectural-truth plan

The canonical dependency policy selects adapter modules across the complete Orket
package. Directory names alone do not define this boundary. Every selected module,
including package initializers and compatibility exports, must declare exactly one
unconditional module-level literal boolean `side_effecting` value. Imported,
conditional, missing, non-boolean and rebound declarations are invalid. The
declaration is collected from the same source bytes as the dependency observations.

The module value bounds the behavior of the adapter surface it exports. `True`
means the surface may mutate external or shared operational state, execute effects,
or own effectful resources. Mixed read/write surfaces declare `True`. `False` means
read-only observation or value processing; it does not promise deterministic purity,
immutable inputs, absence of blocking I/O, or freedom from clock/environment reads.
Existing class declarations remain narrower descriptions of those classes. They
cannot override the module's admission bound. A module declared `False` cannot
contain a class explicitly declared `True`. When present, class declarations obey
the same single, unconditional literal-boolean rule. The module bound covers
classes without a narrower declaration, including inherited adapter surfaces.

Application services retain access to both categories under the dependency policy.
Decision nodes still require an exact adapter entry in that policy's existing
`side_effect_free_adapters` list. Every listed target must exist, be an adapter,
and have a valid `False` module declaration. A listed target cannot reach a `True`
or unclassified adapter through the observed repository dependency graph. Explicit
edge exceptions cannot waive these checks. Listing an adapter is a separate
authority change; classifications never populate the list automatically. The current
list remains empty.

Decision nodes still cannot acquire missing context from filesystem, runtime,
database, environment or hidden caches. A `False` label does not permit such reads.
Review of explicit decision inputs and the truth of each classification remains
necessary. This gate checks declarations and observed dependency admission; it is
not a Python effect system, runtime call graph, hostile-code boundary, or proof
against arbitrary monkeypatching and dynamic state mutation.

The native dependency checker fails closed on classification violations. Export
commands retain their observation-versus-verdict distinction. Reports identify
module declarations, invalid sites and rejected decision admission independently
of ordinary import-direction violations. Stable output paths and diff ledgers remain.
Acceptance requires native negative controls, complete policy-selected inventory,
source/installed binding and preservation of the existing behavioral proofs.
