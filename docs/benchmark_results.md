# CCD/NEXUS local benchmark

Configuration: validators=4, operations per workload=25.

> هذه أرقام محلية لنموذج Python أحادي العملية. لا تمثل latency شبكة أو throughput موزعًا، ولا يجوز مقارنتها مباشرة بأرقام الأوراق المنشورة.

| Workload | Ops/s | p50 finality (ms) | p95 finality (ms) | Messages | Bytes/op |
|---|---:|---:|---:|---:|---:|
| single_domain_independent | 147.0471 | 5.81 | 10.2913 | 300 | 3736.8 |
| single_domain_conflict | 157.2245 | 5.6118 | 8.4147 | 300 | 3736.8 |
| multi_domain_join | 69.1078 | 13.6237 | 19.0655 | 700 | 9845.6 |

## Baseline context

The following are architecture references, not measurements from this run:

| Baseline | Ordering | Fast path | Source |
|---|---|---|---|
| CCD/NEXUS prototype | partial by domain; join for cross-domain operations | local domain certificate | [local implementation](local implementation) |
| HotStuff | global ordered BFT path | leader-driven consensus | [https://arxiv.org/abs/1803.05069](https://arxiv.org/abs/1803.05069) |
| Narwhal/Tusk | DAG dissemination plus consensus ordering | asynchronous dissemination layer | [https://arxiv.org/abs/2105.11827](https://arxiv.org/abs/2105.11827) |
| Sui Lutris-style hybrid | object-local fast path plus consensus for conflicts | consensusless agreement for eligible operations | [https://arxiv.org/abs/2310.18042](https://arxiv.org/abs/2310.18042) |

## Interpretation

The independent workload measures the intended local-domain path. The conflict workload measures repeated writes to one object and is the expected bottleneck case. The multi-domain workload measures atomic Join, not a network-parallel implementation. A valid future comparison must run the same workloads and message sizes against distributed implementations of HotStuff, Narwhal/Tusk, and an object-centric hybrid.
