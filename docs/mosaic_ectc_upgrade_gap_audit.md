# ECTC upgrade gap audit

## Target claim

The revised paper will center on **Evidence-Complete Transition Closure (ECTC)**:

> For every Capsule, the protocol lifecycle terminates in a documented outcome in `{Closed, Conflict, Abandoned}`. A closed outcome binds the predecessor state, Capsule, witness set, and successor StateSeal; a conflict outcome preserves signed ConflictEvidence; and an abandoned outcome preserves an AbandonProof. No terminal outcome is intentionally opaque or unverifiable within the protocol model.

This is a protocol-semantics claim. It is not a claim that MOSAIC invented Ed25519, gossip, SQLite WAL, Reed–Solomon coding, quorum voting, deterministic execution, commit–reveal randomness, or a new consensus algorithm.

## Baseline and required upgrades

| Requirement | Current baseline | Required status in revised paper |
|---|---|---|
| Capsule/Receipt/Closure/Seal lifecycle | Implemented in `mosaic/protocol.py` and `mosaic/model.py` | Reframe as the ECTC abstraction and expose all terminal outcomes |
| Closed/Conflict/Abandoned outcomes | Covered by close, ConflictEvidence, and abandon paths, but not named as one typed outcome | Add an explicit outcome classifier and tests |
| I1--I8 invariants | Existing bounded checks M1--M8 are partial; M5/M8 are tautological and M7 is weak | Replace with named non-trivial invariants and a paper-to-TLA+ mapping |
| Quorum model | Weighted threshold is implemented as `(2*total_weight)//3 + 1`; small unweighted intersection is checked in Python | State an unweighted Model A theorem first; define weighted Model B as an extension |
| Closure exclusivity | Local first-claim locks and conflict evidence are implemented; no complete theorem is currently written | Add assumptions, lemma, and a bounded executable support check; do not call it an unbounded formal proof |
| TLA+ | Models closures, locks, conflicts, abandons, availability, and execution, but includes tautological invariants and abstracts cryptography | Add explicit I1--I8 names and make the finite-bound limitation explicit |
| Adversarial state machine | Focused tests cover close/apply, conflict, abandon/retry, bundle atomicity, signatures, and weighted threshold | Add the 20-case matrix from the revision requirements |
| Disjoint vs. contended workload | Current long run is 120 operations and does not isolate resource independence | Add workloads that vary resource contention and report latency, closures, conflicts, messages, and bytes |
| Batching | BundleClosure exists and has atomicity tests | Add a small single/10/100 closure overhead experiment or explicitly scope bundling as auxiliary |
| Scaling | Current local rehearsals are primarily 4--7 processes and 120 operations | Add at least one scaling dimension and label it LOCAL_EMULATION |
| Byte accounting | Current aggregate is approximately 179 kB per successful operation | Decompose Capsule, receipts, ClosureProof, StateSeal, conflict evidence, framing, event log, and availability bytes |
| Related work | Current references cover major BFT/DAG/payment systems | Add object-centric execution, optimistic concurrency, authenticated state, transaction certificates, and accountable state-machine literature |
| Reproducibility | Public repository, tests, artifacts, figures, and checksums exist | Add one-command reproduction, a fixed tag, and paper links to the tag rather than a moving branch |

## Claim classification to preserve

| Claim | Intended status |
|---|---|
| ECTC lifecycle is executable | Implemented |
| No application without a valid closure | Model-checked and adversarially tested within declared scope |
| Predecessor and successor StateSeal binding | Implemented and tested; formal strengthening required |
| No two incompatible closures under quorum assumptions | Protocol argument plus bounded support check; not an unbounded proof |
| First-claim non-equivocation | Implemented locally and tested; distributed weighted assumptions must be explicit |
| Conflict and abandonment evidence preservation | Implemented and tested |
| Deterministic execution | Tested for the supported instruction kernel |
| Crash recovery | Experimentally observed in local rehearsal |
| Byzantine robustness | Local adversarial rehearsal only |
| WAN liveness | Not evaluated |
| Permissionless Sybil/economic security | Not established |
| Performance superiority | Not claimed |

The upgrade must strengthen the protocol semantics and evidence, not expand the project into zero-knowledge proofs, VDFs, new cryptography, a general smart-contract VM, bridges, wallets, or a public token.
