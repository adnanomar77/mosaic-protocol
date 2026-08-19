# Visual review of manuscript figures

Reviewed on 19 August 2026.

- `mosaic_architecture.png`: 3120 x 884 px, readable labels, no clipping or overlap observed. It shows the Capsule/StateSeal core and supporting network, WAL, settlement, beacon, availability, and event-log layers.
- `capsule_lifecycle.png`: 3120 x 1980 px, readable participants and messages, no clipping observed. It shows witness collection, First-Claim Lock, conflict evidence, closure proof, deterministic execution, successor seal, and event logging.
- Quantitative chart outputs are generated deterministically by `paper/generate_figures.py` from the recorded v3/v5 JSON artifacts; no synthetic measurements are introduced.
