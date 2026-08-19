# ECTC upgrade gap audit — revision after Pasted_content_21

## Target claim

The paper is centered on **Evidence-Complete Transition Closure (ECTC)**:

> For every Capsule, a terminal protocol outcome is represented as `Closed`, `Conflict`, or `Abandoned`. A closed outcome binds the predecessor state, Capsule, witness set, and successor StateSeal; a conflict outcome preserves signed ConflictEvidence; and an abandoned outcome preserves an AbandonProof. If none is available, the local state remains pending rather than being silently classified as success or failure.

This is a protocol-semantics claim. It is not a claim that MOSAIC invented Ed25519, gossip, SQLite WAL, Reed–Solomon coding, quorum voting, deterministic execution, commit–reveal randomness, object-centric execution, or a new consensus algorithm.

## Requirement status

| Requirement | Current state | Remaining action |
|---|---|---|
| Capsule/Receipt/Closure/Seal lifecycle | Implemented and described as ECTC | Preserve as the primary contribution. |
| Closed/Conflict/Abandoned outcomes | Explicit `ECTCStatus`/`TransitionOutcome`, implementation, tests, and measured outcomes | Closed: winner; Conflict: rejected claim with ConflictEvidence; Abandoned: preserved AbandonProof. |
| I1--I8 invariants | Named in paper, TLA+ mapping, Python tests and bounded checks | Keep bounded/formal boundary explicit; strengthen only where implementation supports it. |
| Core quorum model | Model A uses `N >= 3f+1`, quorum `>= 2f+1` | Keep weighted stake as Model B extension, not the core theorem. |
| Closure Exclusivity | Conditional theorem plus executable finite support | Do not call it an unbounded proof or complete consensus proof. |
| TLA+ | ECTC-oriented finite model with named invariants | Remaining limitation: cryptography, reconfiguration, and unbounded execution are abstracted. |
| Adversarial state machine | 20-case matrix and tests | Completed: competing-claims artifact records 1,000 rejected claims and 1,000 ConflictEvidence artifacts. |
| Disjoint vs. contended state | Disjoint row plus genuine same-resource competing-claims row | Completed: 1,000 competing claims produced 1,000 conflicts, 1,000 rejected claims, 1,000 evidence artifacts, and 635 bytes/evidence. |
| Batching | Batch sizes 1/10/100 measured | Keep as supporting infrastructure; do not present bundling as ECTC novelty. |
| Scaling | 4/7/10/16 validator-process local sweep | Keep `LOCAL_EMULATION` scope. |
| Byte accounting | In-process ECTC workload decomposes 3,071.22 bytes/op and batching costs; daemon run reports 184,916.02 bytes/success | Completed: the paper separates accounting domains and the long-run artifact records sent/received bytes by message type. |
| Related work | Added Tango, Block-STM, BFT-CRDTs, Sui Lutris, HotStuff, Narwhal/Tusk, FastPay, Mysticeti, Reed–Solomon, PBFT, BFT-SMR survey, Polygraph, and Attested Append-only Memory | URLs and metadata audited in `paper/reference_status.json`; publisher access restrictions are classified explicitly. |
| Introduction contributions | Already reframed as abstraction, semantics/properties, and executable artifact | Verify final prose does not describe the work primarily as software. |
| Supporting infrastructure | Settlement, randomness, availability, onboarding, networking, and storage are explicitly supporting layers | Keep them out of the novelty center. |
| WAN language | Results are labeled `LOCAL_EMULATION`; independent replication is outside the current evaluation | Replace any wording that makes paper validity depend on future WAN deployment. |
| Reproducibility | Public GitHub repo, fixed final tag, checksums, one-command guide | Completed for `v7.0.0-ectc-paper-final`; push and remote verification remain release steps. |

## Current evidence that must not be conflated

The final daemon long-run reports **184,916.02 bytes per successful operation** from aggregate sent and received counters across the seven-process local rehearsal, with counters by message type. The ECTC workload benchmark reports **3,071.22 non-overlapping protocol bytes per operation** for the current in-process serialized disjoint workload, with explicit Capsule, receipt, closure, StateSeal, framing, and event-log components. These values use different harnesses and accounting domains; the final paper presents both and does not use one as a substitute for the other.

## Claim classification

| Claim | Status |
|---|---|
| ECTC lifecycle is executable | Implemented and tested. |
| No application without a valid closure | Implemented, adversarially tested, and finitely model-checked within declared scope. |
| Predecessor and successor StateSeal binding | Implemented and tested; formal strengthening remains bounded. |
| No two incompatible closures under quorum assumptions | Conditional theorem plus bounded support check; not an unbounded proof. |
| First-claim non-equivocation | Implemented locally and tested; distributed safety depends on stated assumptions. |
| Conflict and abandonment evidence preservation | Implemented, tested, and directly measured in the 1,000-operation competing-claims workload. |
| Deterministic execution | Tested for the supported instruction kernel. |
| Crash recovery | Observed in local rehearsal. |
| Byzantine robustness | Local deterministic adversarial rehearsal only. |
| WAN liveness | Not evaluated; outside the present evaluation scope. |
| Permissionless Sybil/economic security | Not established. |
| Performance superiority | Not claimed. |
| Absolute novelty over all prior work | Not established; the paper claims a specific, falsifiable protocol-semantics composition. |

The upgrade remains focused on protocol semantics and evidence. It does not add ZK, VDF, new cryptography, a general smart-contract VM, bridges, wallets, or a public token.
