# Final PDF visual review

Reviewed `paper/ledger_submission/main.pdf` and `paper/ledger_submission/cover_letter.pdf` after the scientific revision rebuild on 2026-08-19.

| Area | Result |
|---|---|
| First page and metadata | The compiled manuscript no longer displays the placeholder DOI, `LEDGER VOL X`, `Under Consideration`, `ledgerjournal.org`, or other template publication strings. The first page is a neutral submission-safe title page. |
| VCP definition | Pages 5--8 visibly contain the implementation-grounded Valid ClosureProof predicate, the split ClosureDigest definition, the successor-seal condition for Closed, and the conditional Closure Exclusivity theorem. |
| Evidence completeness versus liveness | Page 16 visibly defines liveness as a temporal property separate from evidence completeness and states that ECTC is not an eventual-termination guarantee. |
| Novelty boundary | Pages 14--15 explicitly position ECTC against SMR, certificates, object-centric execution, optimistic concurrency, BFT CRDTs, and accountability prior art. The claim is framed as a semantic interface and not as priority over those mechanisms. |
| Related-work table | Table 6 includes the accountable-agreement comparison row and retains the explicit limitations of the local prototype. It is dense but legible in the rendered PDF. |
| Quantitative results | The workload tables and figures retain the current values: disjoint 3.54/3.63 ms, competing claims 4.19/5.02 ms, 1,000 ConflictEvidence artifacts, 635 bytes/evidence, batch 10 2,530.78 bytes/op, and batch 100 2,473.96 bytes/op. |
| Long-run paragraph | The final text reports p50 36.804089 ms, p95 233.559733 ms, 184,916.02 sent/received bytes per successful operation, the distinct accounting domain from 3,071.22 in-process bytes/op, and message-type counters. |
| Build | Final `main.pdf` is 21 pages and `cover_letter.pdf` is 2 pages. The final LaTeX/BibTeX diagnostics contained no fatal errors, undefined citations, or empty-pages warning. |
| Bibliography | The final bibliography contains 20 entries, all 20 citation keys are used in `main.tex`, and the reference audit reports 15 reachable URLs plus 5 publisher-access-restricted pages with zero transport/HTTP-invalid errors. |
