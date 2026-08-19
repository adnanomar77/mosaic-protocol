# Controlled same-environment comparison

> These rows compare executable abstractions under the same Python process and committee model. They are not official HotStuff, Narwhal/Tusk, or Sui Lutris implementations and must not be cited as their benchmark results.

| Baseline | Workload | Ops/s | p95 ms | Messages/op | Bytes/op |
|---|---|---:|---:|---:|---:|
| CCD/NEXUS | independent | 171.0799 | 5.8251 | 12.0 | 3736.0 |
| HotStuff-style global | independent | 172.1601 | 5.7278 | 12.0 | 3768.0 |
| Narwhal/Tusk-style DAG barrier | independent | 171.8948 | 5.7437 | 16.0 | 4440.0 |
| Sui Lutris-style hybrid | independent | 171.0799 | 5.8251 | 12.0 | 3736.0 |
| CCD/NEXUS | conflict | 172.3141 | 5.7206 | 12.0 | 3736.0 |
| HotStuff-style global | conflict | 172.0628 | 5.7963 | 12.0 | 3768.0 |
| Narwhal/Tusk-style DAG barrier | conflict | 171.5992 | 5.7642 | 16.0 | 4440.0 |
| Sui Lutris-style hybrid | conflict | 172.3141 | 5.7206 | 12.0 | 3736.0 |
| CCD/NEXUS | multi_domain | 78.6383 | 12.7139 | 28.0 | 9844.0 |
| HotStuff-style global | multi_domain | 169.3618 | 5.8095 | 12.0 | 3804.0 |
| Narwhal/Tusk-style DAG barrier | multi_domain | 169.3208 | 5.8101 | 16.0 | 4476.0 |
| Sui Lutris-style hybrid | multi_domain | 169.949 | 5.7871 | 12.0 | 3804.0 |

## Interpretation

The comparison isolates architectural cost under a common implementation substrate. It does not establish production superiority because the reference protocols have different network, cryptographic aggregation, batching, and execution implementations. The valid next step is to replace each abstraction with a real distributed implementation or an official test harness.
