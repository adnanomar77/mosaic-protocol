# Final PDF visual review

Reviewed `paper/ledger_submission/main.pdf` pages 10--12 after the latest benchmark synchronization and final rebuild on 2026-08-19.

| Area | Result |
|---|---|
| Table 3 | The table visibly reports the latest workload values: disjoint 3.54/3.63 ms and 3,071.22 bytes/op; competing claims 4.19/5.02 ms, 4,945.95 bytes/op, and 1,000 conflicts; batch 10 2,530.78 bytes/op; batch 100 2,473.96 bytes/op. The prose reports 635 bytes per rejected claim. |
| Figures 6--7 | Figure 6 visibly uses the refreshed values and labels disjoint, competing claims, and batching. Figure 7 visibly uses the refreshed local scaling sweep and states that it is not WAN throughput evidence. |
| Table 5 | The byte decomposition visibly reports 707,548 event-log bytes and a 3,071,218-byte total, or 3,071.22 bytes/op, for the current in-process disjoint workload. |
| Long-run paragraph | The final text visibly reports p50 36.804089 ms, p95 233.559733 ms, 184,916.02 sent/received bytes per successful operation, the distinct accounting domain from 3,071.22 in-process bytes/op, and message-type counters. |
| Build | Final `main.pdf` is 19 pages and `cover_letter.pdf` is 2 pages. The final LaTeX/BibTeX diagnostics contained no fatal errors, undefined citations, or empty-pages warning. |
