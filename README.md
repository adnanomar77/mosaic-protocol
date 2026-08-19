# MOSAIC Protocol

MOSAIC (Mutual-Obligation State And Integrity Capsules) is an executable research prototype for a state-transition-centric distributed ledger. Its central research semantics is **Evidence-Complete Transition Closure (ECTC)**: an observed Capsule ends in a documented `Closed`, `Conflict`, or `Abandoned` outcome, while an unobserved outcome remains explicitly pending. Its primary protocol objects are `Capsule`, `WitnessReceipt`, `ClosureProof`, `StateSeal`, `ConflictEvidence`, and `AbandonProof`.

The implementation explores whether a ledger can make the authenticated state transition—not only a globally ordered block—the main integrity boundary. It includes a leaderless TCP gossip layer, Ed25519 signatures, optional mTLS, SQLite WAL durability, weighted membership and settlement, commit–reveal randomness, Reed–Solomon availability, deterministic execution, onboarding, beacon networking, availability networking, and a hash-chained event log. The `ccd_nexus` package contains shared cryptographic primitives and legacy domain support used by the MOSAIC implementation.

## Scientific status

The repository is a research artifact. The current reported evaluation is **LOCAL_EMULATION** on one host: seven daemon processes, 120 operations, a scheduled kill/restart, two Byzantine test identities, and partial-frame probes. The final local run completed 120/120 operations with liveness ratio 1.0, zero unexpected operational errors, p50 36.804089 ms, p95 233.559733 ms, and a verified eight-event hash-chained log. Its aggregate sent/received counter was 184,916.02 bytes per successful operation across the seven processes; this is distinct from the 3,071.22 bytes/op in the in-process disjoint workload. The final revision collects 102 tests and includes a 20-case adversarial matrix, genuine competing-claims evidence, disjoint/batched workloads, validator-process scaling, message-type byte counters, and byte decomposition. These results do not establish public-WAN performance, permissionless deployment, a production mainnet, or universal superiority over existing ledgers.

## Requirements

Python 3.11 or newer is required. Install the package and test dependencies with:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## Verification

```bash
python3 -m pytest -q
python3 benchmarks/security_audit.py
python3 benchmarks/fuzz_mosaic_wire.py
PYTHONPATH=. python3 -m benchmarks.model_check_mosaic
PYTHONPATH=. python3 benchmarks/run_mosaic_ectc_workloads.py --operations 1000
PYTHONPATH=. python3 paper/generate_figures.py
python3 benchmarks/audit_submission_artifacts.py
```

## Local long-run rehearsal

```bash
python3 -m benchmarks.run_mosaic_testnet_long \
  --nodes 7 \
  --operations 120 \
  --base-port 22620 \
  --data-dir /tmp/mosaic-testnet-long \
  --event-log testnet/events/testnet-0.jsonl
```

The harness writes JSON metrics and a hash-chained event log. It is intentionally marked local emulation until independent operators run validators on independent WAN hosts with operator-controlled keys.

## Manuscript and artifacts

The Ledger submission package is under `paper/ledger_submission/`. The source manuscript is `main.tex`; the compiled PDF is generated locally from the official Ledger class; references are in `references.bib`; figures and CSV data are under `figures/` and the submission directory. The ECTC theorem and model are under `formal/`; the adversarial matrix is under `docs/mosaic_adversarial_test_matrix.md`; the workload artifact is `docs/mosaic_ectc_workloads.json`; and the main long-run artifact is `testnet/artifacts/mosaic_testnet_long_final.json`. See `REPRODUCE.md` for the one-command sequence.

The companion research paper is:

> Adnan Omar Awad Allemon, “MOSAIC: State-Transition-Centric Integrity Capsules for Distributed Ledger Execution.” Submission under consideration at Ledger.

## Reproducibility and security

Private keys, access tokens, host credentials, and virtual environments are excluded from this repository. Do not reuse keys generated for experiments in a public network. Before any WAN deployment, perform an independent security review, formalize the weighted-quorum and reconfiguration model, and run the gates on independent hosts.

## License

The implementation is released under Apache-2.0. The manuscript and documentation are intended to be released under CC BY 4.0 where applicable; see the notices in the submission package.

## AI-use disclosure

AI-assisted tools were used during code inspection, drafting support, organization, and language editing. The author is responsible for verifying the implementation, experiments, references, claims, and final manuscript. The paper contains an explicit disclosure because Ledger requires authors to disclose AI use.
