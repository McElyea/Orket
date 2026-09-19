# Extension source origin and load ownership

Owner: Orket Core
Date: 2026-09-19
Effective version: 0.6.33 (patch, breaking admission correction)
Status: Active implementation contract; checkpoint proof is recorded in the canonical plan

## Delta

Previously, legacy and direct SDK loaders inserted an extension root into
`sys.path`, then accepted whatever `importlib` returned. Python's process-wide
cache could return another root's module with the same name. The selected source
was validated without checking that the adopted object came from it. Validation
also preferred a same-named file over a package and omitted parent initializers.

All four entrypoint paths now use the side-effecting adapter
`orket/adapters/execution/extension_modules.py`: legacy registration, direct SDK
construction, SDK child execution and governed-agent child construction.

1. Module components must be Python identifiers. `orket` and `orket_extension_sdk`
   are reserved entrypoint roots. These restrictions do not change imports of
   admitted SDK contracts from extension code.
2. The selected root must be a directory. Every selected Python source and package
   path resolves inside it. Regular packages take precedence over same-named files.
   Namespace parents are supported; the selected leaf requires Python source.
3. Application validation checks every selected parent initializer and the leaf
   source. Existing host-import and declared-stdlib policy remains applicable.
   SDK child execution revalidates those sources before loading.
4. Before importing, cached selected modules and parents must have matching spec
   identity, origin, file and package search paths. Imports are checked again
   before registration, construction or run-callable adoption.
5. A mismatch raises `E_EXT_MODULE_ORIGIN_MISMATCH` with the selected and observed
   origins. It never silently replaces cached modules or registers the wrong
   workload. Invalid names and escaping sources have explicit refusal codes.
6. A process-wide reentrant lock serializes this loader's path admission through
   immediate registration/construction. The exact temporary path insertion is
   removed on success or failure; existing path entries are retained. SDK and
   agent children keep their pre-existing process-lifetime extension search path.
7. Legacy registration and SDK preflight source reads use owned workers. Caller
   cancellation, repeated cancellation or timeout cannot finish until that worker
   settles. A worker failure remains observable. The agent child likewise owns
   its loading worker.

## Migration and limits

Use distinct top-level module names when loading different legacy/direct-SDK
extension roots in one process, or start a fresh process. Reusing the selected
root retains normal Python module-cache behavior. This is not hot reload: edits
to already loaded source require restarting the process. Tests representing
independent extensions must also use independent module identities.

This contract verifies the selected entrypoint and its package parents. It does
not attest executed source bytes, recursively verify every transitive or later
dynamic import, evict cached helper modules, or fence concurrent external source
editors. Existing extension import policy remains separate from source identity.
Python import hooks, source checks and child processes are not OS containment;
the admitted posture remains trusted extension code. CAP-2 stays open.

Imports, parent initializers and registration callbacks can have effects before
failure. There is no rollback of those effects or of Python's module cache.
Selected source validation and subsequent imports are not one filesystem snapshot.
Other actors that mutate `sys.path`, import hooks or cached module metadata do not
participate in this loader's lock.

Worker retention does not establish termination of arbitrary trusted extension
code. A hung registration worker can delay cancellation indefinitely. Legacy
compile/validator/summary callbacks, SDK process lifetime and the remaining
extension execution effects still require the full D assessment. No cancellation
or teardown guarantee is added for those later phases here.

## Validation gates

Real subprocess fixtures cover both loader APIs, conflicting roots, valid repeat
loads, independent module names, package-parent conflicts, namespace parents,
constructor imports, package precedence, parent import policy and package search
path redirection before leaf execution. Real application registration and source
validation workers exercise controlled interruption. The independent filesystem
operation bound is 0.5 seconds; released-worker settlement is bounded at 3 seconds
in the tests. These are controlled trusted-code proofs, not hostile containment.

Existing extension manager, SDK import-guard and governed-agent subprocess flows
remain in the affected cohort. Both Quality jobs include the new tests. Package
and four native Windows/Linux Python 3.11/3.12 gates must pass before checkpointing.
Dependency analysis remains fail-closed on the unresolved loader/guard routes;
this change introduces no policy exception or special analyzer exemption.

## Rollback and versioning

Rollback triggers include wrong-origin adoption, changed valid workload results,
lost worker retention or package/native regressions. Revert the complete versioned
change and its authority/workflow updates together, preserving failed evidence.
Restart affected interpreters; a source revert cannot repair an existing cache or
undo extension effects. Re-admission needs verified selected origins.

The patch version records a stricter admission contract and failure behavior.
There is no compatibility shim that reinstates wrong-root adoption. This candidate
does not complete C/D, the capability gates or whole-lane acceptance.
