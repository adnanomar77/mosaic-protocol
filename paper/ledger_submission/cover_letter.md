# Cover Letter

**19 August 2026**

Editors of *Ledger*  
University of Pittsburgh

Dear Editors,

I submit the manuscript **“MOSAIC: State-Transition-Centric Integrity Capsules for Distributed Ledger Execution”** for consideration as a full-length research article in *Ledger*.

The manuscript introduces **Evidence-Complete Transition Closure (ECTC)**, a protocol semantics in which a state transition is not terminal merely because a validator accepted it. A Capsule must reach a verifiable *Closed* outcome carrying a ClosureProof and successor StateSeal, a *Conflict* outcome carrying ConflictEvidence, or an *Abandoned* outcome carrying an AbandonProof. The lifecycle binds predecessor state, transition claim, witness obligation, and successor state while preserving incompatible and abandoned claims as independently inspectable artifacts. The implementation connects this lifecycle to leaderless dissemination, durable SQLite WAL recovery, Ed25519 signatures, weighted membership and settlement, commit–reveal randomness, Reed–Solomon availability, deterministic execution, onboarding, and a hash-chained event log.

The paper makes three contributions: the ECTC lifecycle and outcome classifier; an explicit Valid ClosureProof predicate requiring context binding, unique signer/receipt correspondence, individually valid ACCEPT receipts, threshold weight, and canonical proof-digest recomputation, together with a conditional quorum-intersection argument and bounded TLA+ support; and a reproducible artifact with adversarial tests, disjoint-versus-competing-claims workloads, batching, scaling, and byte decomposition. The manuscript separately defines Evidence Completeness as a state-observation property and Liveness as a temporal property, so ECTC is not presented as an eventual-termination guarantee. The implementation currently collects 102 automated tests. In a 1,000-operation serialized local workload, disjoint and genuine competing-claims cases measured 3.54/3.63 ms and 4.19/5.02 ms p50/p95 latency, respectively; the competing-claims run rejected 1,000 losing claims and generated 1,000 ConflictEvidence artifacts at 635 bytes per rejected claim on average, while batch sizes of 10 and 100 measured 2,530.78 and 2,473.96 protocol bytes per successful operation. In a seven-process local rehearsal with two Byzantine test identities, a scheduled kill/restart, and partial-frame probes, all 120 requested operations succeeded. The measured liveness ratio was 1.0, unexpected operational errors were zero, median latency was 36.804089 ms, and p95 latency was 233.559733 ms. These measurements are explicitly identified as LOCAL_EMULATION results from one host. They are not Internet-WAN measurements, proof of permissionless Sybil resistance, a production-mainnet claim, or evidence of universal superiority over adjacent ledgers.

The work is relevant to *Ledger* because it addresses a general problem in cryptocurrency and distributed-ledger protocol design: how state transitions, conflicting claims, execution results, availability evidence, and recovery decisions can be represented as one auditable object lifecycle. The related-work section treats object-centric execution, optimistic concurrency, selective ordering, certificates, and BFT CRDTs as prior art; the manuscript does not claim that ECTC is the first use of any of those ideas. The narrower falsifiable claim is that ECTC provides a semantic interface in which positive and negative terminal outcomes are evidence-complete while Pending remains non-terminal; it does not claim priority over the individual mechanisms it composes. The public repository contains the source code, tests, formal model, adversarial matrix, benchmark drivers, figures, tabular data, JSON artifacts, and checksums needed to inspect and reproduce the reported local experiment:

<https://github.com/adnanomar77/mosaic-protocol>

The repository is public and excludes private keys, credentials, and local virtual environments. The code is released under Apache-2.0; the manuscript and documentation are released under CC BY 4.0 where applicable.

An AI-assisted software and language workflow was used during development and manuscript preparation for code inspection, drafting support, organization, and language editing. The author reviewed the implementation, ran the experiments, checked the cited sources, verified the reported numbers, and remains solely responsible for the manuscript, its claims, its limitations, and the final submission. This use is disclosed in the manuscript in accordance with *Ledger*’s AI policy.

The manuscript is original, is not under consideration elsewhere, and has not been published in a peer-reviewed venue. No external funding was received. The author declares no known conflicts of interest relevant to this submission.

## Suggested reviewers

The following scholars are suggested because their public institutional profiles document expertise directly relevant to distributed consensus, blockchain protocols, cryptographic security, and reproducible distributed systems. The author has no known personal, institutional, supervisory, employment, or recent co-authorship relationship with any of them. The editor should exclude any candidate for whom an undisclosed conflict or availability issue is identified; none has been contacted or has agreed to review.

1. **Christian Cachin** — Professor of Computer Science, University of Bern. Expertise: blockchain and consensus protocols, distributed computing, cryptographic protocols, and cloud-computing security. Public institutional email: `christian.cachin@unibe.ch`. Profile: <https://crypto.unibe.ch/cc/>

2. **Rachid Guerraoui** — Full Professor, Distributed Computing Laboratory, EPFL. Expertise: distributed algorithms, secure distributed storage, transactional shared memory, distributed programming languages, and robust distributed computing. Public institutional email: `rachid.guerraoui@epfl.ch`. Profile: <https://people.epfl.ch/rachid.guerraoui?lang=en>

3. **Elaine Shi** — Professor of Computer Science and Electrical and Computer Engineering, Carnegie Mellon University. Expertise: blockchain, cryptography, distributed systems security, formal methods, protocol security, and verification. Public institutional email: `rshi@andrew.cmu.edu`. Profile: <https://www.cylab.cmu.edu/directory/bios/shi-elaine.html>

Thank you for considering this submission. I would welcome a rigorous review of both the protocol hypothesis and the limits of the current evidence.

Sincerely,

**Adnan Omar Awad Allemon**  
Independent Researcher  
Corresponding author: <adnanomar774@gmail.com>
