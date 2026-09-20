# Bounded dynamic import analysis

Owner: Orket Core. Date: 2026-09-20. Candidate version: 0.6.43.

The dependency policy remains v2. No analysis-error waiver, new edge exception,
layer exemption or runtime import bypass is introduced. Unknown dynamic targets
remain failures; source inventory, source hashes and cycle checks retain authority.

## Import interception

The scanner may recognize installation of an argument-preserving wrapper on
`builtins.__import__` or `importlib.import_module`. It must inspect the actual
factory definition in the same Git-visible source inventory, including an
explicitly imported factory. It does not trust a function name, annotation,
comment, filename or allowlist.

Recognition requires an unambiguous, undecorated factory returning one nested
function. That function forwards every original positional parameter, in order,
to the captured importer, and never rebinds those parameters or exposes the
captured importer elsewhere. A bounded validation prefix may inspect the inputs
through another factory parameter before delegation. Installation must replace
the same standard importer it captures. Unknown callbacks, changed targets,
reordered/dropped arguments, decorators, ambiguous bindings and other capability
escapes remain diagnostics. Recognized interceptions are reported separately;
ordinary imports and unresolved routes in both modules are still analyzed.

This recognizes the import request's original caller as its dependency source.
It does not make arbitrary callbacks transparent, prove hook side-effect safety,
infer a runtime call graph, or establish hostile-code containment.

## Absolute external names

Extension module resolution and cache/import lookup will share one runtime name
validator. It rejects string subclasses and other non-plain strings, relative
names, and the reserved `orket` and `orket_extension_sdk` namespaces before any
lookup. Existing identifier, root-containment and actual-origin checks remain.

The scanner may infer an external name only from an unambiguous function whose
inspected body rejects non-plain strings, relative names and the complete scanned
namespace, then returns the same unmodified argument. It must require every guard,
track a validated local assignment before lookup, invalidate rebindings, and avoid
assuming facts across closures, comprehensions or non-dominating branches. A
recognized lookup is reported as outside the scanned package, never as a resolved
repository edge. Missing guards, relative-name admission, unknown validators,
namespace mutation and subsequent name replacement remain analysis failures.

This is a bounded syntactic proof, not general Python dataflow inference. It
preserves the failure verdict for unsupported patterns. Callers provide ordinary
absolute module-name strings; string subclasses are no longer admissible at the
extension-name boundary. No claim is made about dependencies executed by trusted
extension code outside the scanned repository package.

## Acceptance and migration

Native checker fixtures must demonstrate accepted forwarding controls and
rejected redirected, escaped, rebound and ambiguous variants. A forbidden import
after hook installation must still fail. Existing dependency/extension admission
tests remain required. External-name controls must cover missing guards, relative
names, string-subclass behavior, rebindings, branch/closure scope, real extension
origins and rejected reserved namespaces. The six original diagnostics and failed
pre-change probes stay retained; successful bounded analysis must report its
recognized routes without erasing the historical failures.

Reports add explicit recognized-route observations. Existing policy fields and
failure semantics remain unchanged. Update the generated graph, active authority
and contributor guidance with the implementation. Rollback code and report
consumers together; retain all prior receipts and do not relabel a failed verdict.
