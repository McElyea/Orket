# Extension catalog representation

Last updated: 2026-09-25
Status: Active implementation contract; scoped acceptance belongs to the architectural-truth plan

Implementation status: the null/default correction has scoped source proof.
The explicit generic reference writer correction has a reached counterexample
and scoped source closing, including real Git installation and process restart
for both absent and explicit references. Complete source/installed acceptance
remains open.

Installing, listing and restarting an installed generic SDK extension must retain
the same complete `ExtensionRecord`. Source/checkout identity, manifest digest,
security posture, configuration sections, capabilities and workload metadata
remain part of that equality. A successful installation alone does not prove
lossless catalog readback.

For `sdk_v0` workload entries, absent or null optional input/output contract
references have the canonical in-memory value `""`. The shared SDK normalizer
maps only `None` to that value. Non-null values retain the established string
conversion and whitespace trimming; literal `"None"` is not a null sentinel.
SDK manifest validation and governed-agent contract requirements still apply.
The catalog resolves each entry's style from its own declaration, then the
record style. Legacy and other styles retain their prior reference conversion.

An empty or missing `register_callable` receives the `register` fallback only
outside the exact `sdk_v0` record style. SDK records keep the empty value and
explicit nonempty callable metadata remains unchanged. This does not enable a
legacy registration callback for SDK workloads or change execution dispatch.

There is no catalog schema rewrite or reinstallation requirement. Existing
catalog rows are interpreted by their existing reader; typed manifest parsing
and catalog construction share the SDK optional-reference normalizer. Generic
catalog rows persist each nonempty SDK input/output reference independently and
omit empty references and unused agent-only fields. The existing strict agent
discriminator runs before the generic SDK write branch. This preserves admitted
metadata without interpreting a reference or adding admission authority.
Legacy and unknown write styles keep their existing compact shape. Agent records retain
their validated nonempty contracts and declaration. Existing legacy ASCII
digest serialization remains unchanged.

The catalog/file owner, installation command supervisor, admission policy,
source-origin checks, Git deadlines and required cleanup remain authoritative.
The correction grants no repair, deletion, rollback or hostile-code authority.
Entrypoint-only discovery is a separate path requiring its own proof.
Migration: `docs/architecture/CONTRACT_DELTA_EXTENSION_CATALOG_REPRESENTATION_D_2026-09-25.md`.
