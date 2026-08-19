# CCD/NEXUS committee-size sweep

Operations per workload: 20. Local single-process measurements only.

| Validators | Workload | Ops/s | p95 finality (ms) | Messages/op | Bytes/op |
|---:|---|---:|---:|---:|---:|
| 4 | single_domain_independent | 171.1322 | 5.7862 | 12.00 | 3736.0 |
| 4 | single_domain_conflict | 170.9962 | 5.8411 | 12.00 | 3736.0 |
| 4 | multi_domain_join | 78.796 | 12.7833 | 28.00 | 9844.0 |
| 7 | single_domain_independent | 103.8532 | 9.76 | 21.00 | 6538.0 |
| 7 | single_domain_conflict | 105.52 | 9.5501 | 21.00 | 6538.0 |
| 7 | multi_domain_join | 47.8852 | 20.9673 | 49.00 | 17227.0 |
| 10 | single_domain_independent | 74.8589 | 13.3818 | 30.00 | 9340.0 |
| 10 | single_domain_conflict | 74.5742 | 13.3956 | 30.00 | 9340.0 |
| 10 | multi_domain_join | 34.2389 | 29.411 | 70.00 | 24610.0 |
