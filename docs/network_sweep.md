# Distributed TCP network sweep

> Localhost multi-process results. They validate transport integration and fault handling, not Internet-scale performance.

| Nodes | Scenario | Success | p50 ms | p95 ms | Drop events | Retries | Equivocations | Errors |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 4 | healthy | 5/5 | 13.3650 | 13.4843 | 0 | 0 | 0 | 0 |
| 4 | delay_drop_retry | 5/5 | 18.9325 | 19.3490 | 10 | 10 | 0 | 0 |
| 4 | one_byzantine | 5/5 | 13.7411 | 13.9463 | 0 | 0 | 10 | 0 |
| 7 | healthy | 5/5 | 19.7602 | 22.4655 | 0 | 0 | 0 | 0 |
| 7 | delay_drop_retry | 5/5 | 24.8153 | 25.0027 | 20 | 20 | 0 | 0 |
| 7 | one_byzantine | 5/5 | 20.5241 | 22.6071 | 0 | 0 | 10 | 0 |

## Interpretation

Healthy and one-Byzantine scenarios should preserve successful operations when the Byzantine weight is below one third. The delay/drop scenario tests retries and may increase p95. A localhost result does not establish production safety or WAN performance.
