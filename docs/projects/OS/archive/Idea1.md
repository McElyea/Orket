You’re thinking about it the right way: “core law” + “optional kernel modules” is how you get both identities without lying about either.

The only trap is this: modularity doesn’t automatically solve the identity problem unless the boundaries are constitutional and enforced. If the “OS bundle” can reach in and change core invariants, you’ll end up with a blob.

So here’s the clean way to do what you’re describing.

The rule that makes “Core + OS bundle” real

Core is a spec + validator + event contract.
Everything else is a host.

That means:

Orket Core (Control Plane): defines ontology, stages, policies, determinism, logging law, error namespaces.
It does not do scheduling, isolation, drivers, runtime lifecycle, or persistence beyond what’s needed to evaluate artifacts.

Orket Hosts: implement execution, scheduling, sandboxing, storage, networking.
Hosts can be swapped without changing Core semantics.

If you keep that boundary, you can legitimately offer:

“Control Plane only” install

“OS bundle” install
…and both are true.

Your “click OS selects 6 modules” UI: make it a profile, not a fork

Think in terms of install profiles that select modules:

Profile: core

orket-core (schemas, gatekeeper, sentinel, log contract)

orket-cli (thin runner to invoke core checks)

Profile: workstation

core +

orket-daemon (local long-running host)

orket-cache (content-addressed store, optional)

orket-model-provider-ollama (or other local providers)

Profile: mesh/offline

workstation +

orket-sync (artifact exchange, signed bundles, optional)

orket-policy-distribution (policy/package propagation)

Profile: OS bundle

workstation +

orket-scheduler

orket-capabilities

orket-sandbox

orket-drivers (storage/model/network)

orket-runtime-contracts (host interface)

Same core. Different host responsibilities.

The “kernel” question: what would actually make it OS-class?

Not branding. These 4 things:

Process model (what is a task? lifetime? cancellation? retries?)

Capability model (what is an agent/tool allowed to do? how is it enforced?)

Isolation boundary (sandboxing, filesystem/net access, secrets)

Driver contracts (storage/model providers/schedulers as replaceable implementations)

If you never build those, you still have a great control plane.
If you do build them as optional modules, you have an OS-class substrate—without corrupting the core.

The hard architectural requirement (non-negotiable)

Core must be able to validate the outputs of any host without trusting that host.

Meaning:

host proposes artifacts

core adjudicates legality (stages/policy/determinism)

host never “overrides” core rules

all host activity is observable via core’s event contract

That’s what keeps it constitutional.

What I’d crystallize first (if you want maximum leverage)

Do the module graph first. It forces crisp boundaries and prevents blob-formation.

Here’s a starter graph (minimal, realistic):

Core

orket-core-law (schemas, stage model, vocab, raw-id policy, determinism)

orket-gatekeeper (5-stage validator)

orket-sentinel (diff + triplet gating + CI interface)

orket-event-contract (logging + codes + locations)

Interfaces

orket-host-api (how hosts submit artifacts/events to core)

orket-driver-api (storage/model/sandbox drivers)

Hosts

orket-cli-host (runs locally, no daemon)

orket-daemon-host (long-running, queue/scheduler optional)

OS modules

orket-scheduler

orket-capability-manifest

orket-sandbox-driver-* (none/local jail/firejail/windows job objects)

orket-storage-driver-* (fs, sqlite, CAS)

orket-model-driver-* (ollama, llama.cpp, etc.)

orket-sync (mesh exchange, offline bundle propagation)

Profiles

core

workstation

mesh

os

That’s enough to make your UI idea real.