
## Block-STM

Source: arXiv `2203.06871v3`, *Block-STM: Scaling Blockchain Execution by Turning Ordering Curse to a Performance Blessing*.

The abstract describes Block-STM as a parallel execution engine built around software transactional memory. Transactions execute speculatively, dependencies are detected dynamically, and the deterministic outcome is consistent with a preset order. This is prior art for optimistic concurrency, deterministic parallel execution, and workload-dependent conflict rates. MOSAIC should not claim novelty for deterministic execution or conflict-aware parallel processing. The distinction proposed in the revised paper is that ECTC makes the transition's closure evidence and terminal outcome explicit at the protocol boundary; the benchmark only measures MOSAIC's supported kernel and does not compare throughput with Block-STM.

URL: https://arxiv.org/abs/2203.06871

## Process-Commutative Distributed Objects / BFT CRDTs

Source: arXiv `2311.13936v2`, *Process-Commutative Distributed Objects: From Cryptocurrencies to Byzantine-Fault-Tolerant CRDTs*.

The abstract studies the space between BFT CRDTs and totally ordered ledgers, uses Mazurkiewicz traces to characterize legal operation sequences, and presents a generic algorithm for crash and Byzantine settings. This is direct prior art for reduced ordering scope, commutativity, and Byzantine conflict-free objects. MOSAIC should position ECTC as an evidence/accountability lifecycle rather than as a new CRDT or a first system to avoid global ordering.

URL: https://arxiv.org/abs/2311.13936
