# Ledger submission package

This directory contains the ECTC-centered manuscript and submission materials for *Ledger*. The manuscript reports a bounded, reproducible protocol and systems artifact; it does not claim WAN deployment, permissionless security, production readiness, or universal ledger superiority.

| File | Purpose |
|---|---|
| `main.tex` | Source manuscript using the official Ledger class. |
| `main.pdf` | Rebuilt submission PDF. |
| `references.bib` | BibTeX bibliography with DOI/arXiv or official web URLs. |
| `cover_letter.tex` | Two-page cover-letter source. |
| `cover_letter.pdf` | Rebuilt cover letter for submission. |
| `cover_letter.md` | Plain-text/Markdown version of the cover letter. |
| `figures/` | Figure sources, rendered images, and quantitative CSV/plot outputs. |
| `images/` | Ledger template logos and required class assets. |
| `final_visual_review.md` | Record of the local visual review of the generated PDFs. |
| `checksums.sha256` | Checksums for the fixed submission package. |
| `ectc_workloads.csv` | Workload, batching, scaling, and byte-accounting data. |

## Rebuild the manuscript

From the repository root:

```bash
cd paper/ledger_submission
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

## Rebuild the cover letter

```bash
cd paper/ledger_submission
pdflatex -interaction=nonstopmode -halt-on-error cover_letter.tex
```

The publication fields in `ledger.cls` remain placeholders (`VOL X`, `X-X`, and a placeholder DOI) because they are assigned by the journal after acceptance. The manuscript is marked as a submission under consideration and must not be represented as published Ledger content before editorial acceptance. The current repository revision collects 101 automated tests; all evaluation rows are explicitly marked as LOCAL_EMULATION or in-process serialized measurements.

The formal argument is in `formal/ectc_safety_argument.md`, the bounded model is in `formal/mosaic_safety.tla`, the adversarial state-machine matrix is in `docs/mosaic_adversarial_test_matrix.md`, and the reproducibility commands are in `REPRODUCE.md`.
