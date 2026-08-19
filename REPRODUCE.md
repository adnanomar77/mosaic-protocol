# Reproduction guide for the MOSAIC ECTC artifact

This repository contains the MOSAIC implementation and the paper artifact for **Evidence-Complete Transition Closure (ECTC)**. The commands below reproduce the reported local checks and measurements. They do not create a WAN testnet and do not establish permissionless or production security.

## Environment

The reference environment uses Python 3.11 or newer. Install the package in an isolated environment, then run from the repository root.

```bash
python3 -m pip install -e .
```

## One-command validation sequence

```bash
python3 -m pytest -q
PYTHONPATH=. python3 -m benchmarks.model_check_mosaic
PYTHONPATH=. python3 benchmarks/run_mosaic_ectc_workloads.py --operations 1000
PYTHONPATH=. python3 paper/generate_figures.py
```

The final artifact revision currently collects **102 tests**. The bounded model checker reports finite unweighted quorum cases, weighted support, ECTC outcome checks, bundle atomicity, availability checks, and deterministic-execution checks. The workload benchmark writes `docs/mosaic_ectc_workloads.json` and `paper/ledger_submission/ectc_workloads.csv`.

## Long-run rehearsal

```bash
python3 -m benchmarks.run_mosaic_testnet_long \
  --nodes 7 --operations 120 --base-port 22620 \
  --data-dir /tmp/mosaic-testnet-long \
  --event-log testnet/events/testnet-0.jsonl
```

The long-run command is a seven-process **LOCAL_EMULATION** rehearsal. It must not be described as a WAN or public-testnet measurement.

## Manuscript build

```bash
cd paper/ledger_submission
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error cover_letter.tex
```

The Ledger class contains publisher-assigned placeholders for volume, pages, and DOI. These fields are not publication metadata until the journal assigns them.

## Artifact boundaries

The repository intentionally excludes private keys, credentials, local virtual environments, and runtime WAL data. The TLA+ model is finite and abstracts cryptography. The quorum theorem in `formal/ectc_safety_argument.md` is conditional on its stated assumptions. The current experiments are local and serialized or process-local; they do not establish WAN liveness, Sybil resistance, economic security, or performance superiority over other ledgers.
