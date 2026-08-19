# MOSAIC network experiment matrix

All runs used five operations per scenario on independent localhost TCP processes.

| Nodes | Scenario | Success | p50 ms | p95 ms | Drops | Retries | Leader conflicts | Errors |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 4 | healthy | 5/5 | 5.1894 | 5.4177 | 0 | 0 | 0 | 0 |
| 7 | healthy | 5/5 | 8.4121 | 10.8179 | 0 | 0 | 0 | 0 |
| 4 | delay 1ms + drop 10% | 5/5 | 10.3768 | 10.8479 | 3 total observed across nodes | 3 total observed across nodes | 0 | 0 |
| 7 | delay 1ms + drop 10% | 5/5 | 13.8462 | 14.6602 | 15 total observed across nodes | 15 total observed across nodes | 0 | 0 |
| 4 | one Byzantine (`w1`) | 5/5 | 5.5886 | 5.9917 | 0 | 0 | 5 | 0 |
| 7 | one Byzantine (`w1`) | 5/5 | 8.1282 | 8.2001 | 0 | 0 | 5 | 0 |

The Byzantine case injected a signed `ACCEPT` followed by a signed `ABANDON` for the same capsule. The leader counted the second distinct receipt as a conflict and did not count it toward the ACCEPT quorum. These are localhost tests, not WAN or production measurements.
