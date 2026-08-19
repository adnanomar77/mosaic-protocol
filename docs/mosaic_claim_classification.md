# MOSAIC claim classification

| Claim | Classification | Evidence boundary |
|---|---|---|
| The Capsule–WitnessReceipt–ClosureProof–StateSeal lifecycle is executable | Implemented | Python reference implementation and focused tests |
| Every observed terminal outcome is Closed, Conflict, or Abandoned when an outcome is available | Implemented | `mosaic/ectc.py`, `MosaicProtocol.transition_outcome`, ECTC tests |
| Closed requires a ClosureProof and successor StateSeal | Implemented and tested | ECTC tests and model-check support |
| No application without a verified closure | Implemented and model-checked | `apply`, bounded model checks, adversarial tests |
| Predecessor and successor binding | Implemented and tested | Capsule validation, closure verification, execution-binding tests |
| No two incompatible closures under quorum assumptions | Theorem-supported and bounded-model checked | `formal/ectc_safety_argument.md`, Model A/B checks; not an unbounded executable proof |
| First-claim non-equivocation | Implemented locally and tested | First-claim lock and conflict evidence tests; distributed deployment assumptions remain explicit |
| Conflict and abandonment evidence preservation | Implemented and tested | `ConflictEvidence`, `AbandonProof`, ECTC tests |
| Deterministic execution for supported instruction kernel | Experimentally tested | Execution tests; not a general smart-contract VM claim |
| Crash/WAL recovery | Experimentally observed locally | Production persistence test and local long-run |
| Malformed/oversized/partial frame resilience | Experimentally tested locally | Network-limit tests; not WAN DoS evidence |
| Availability repair and sampling | Experimentally tested locally | Erasure and availability-store tests |
| Permissionless Sybil resistance | Not established | Requires independent WAN operators and admission economics study |
| Economic security | Not established | Settlement implementation exists, but no adversarial economic study is claimed |
| WAN liveness | Not evaluated | Current long-run and workload results are LOCAL_EMULATION |
| Performance superiority over other ledgers | Not claimed | No cross-system apples-to-apples claim is made |
