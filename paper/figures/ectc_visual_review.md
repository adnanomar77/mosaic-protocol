# ECTC figure visual review

The generated ECTC workload-latency figure was inspected at 3909x2349 pixels. It clearly shows p50/p95 bars for disjoint, same-resource, batch-10, and batch-100 workloads. Numeric annotations are legible, the axis label states per-operation latency in milliseconds, and no clipping or overlap was observed.

The generated local scaling figure was inspected at 3549x2229 pixels. It clearly shows the serialized operations/s curve for 4, 7, 10, and 16 validator processes. The title explicitly says local scaling and disjoint workload, and the axes are legible without visual clipping.

Both figures are generated from `docs/mosaic_ectc_workloads.json` by `paper/generate_figures.py`. They are local in-process measurements and must not be described as WAN or production performance.
