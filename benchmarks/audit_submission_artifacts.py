from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
artifact = ROOT / "testnet/artifacts/mosaic_testnet_long_final.json"
checksums = ROOT / "testnet/artifacts/mosaic_public_testnet_v5_checksums.txt"

with artifact.open(encoding="utf-8") as handle:
    result = json.load(handle)

assert result["operations_requested"] == 120
assert result["operations_successful"] == 120
assert result["liveness_ratio"] == 1.0
assert result["safety_signal"]["errors"] == 0
assert result["event_log_verified"] is True
assert checksums.exists()

print("artifact_validation=passed")
print({
    key: result[key]
    for key in (
        "nodes",
        "operations_requested",
        "operations_successful",
        "liveness_ratio",
        "p50_ms",
        "p95_ms",
        "cost",
        "event_count",
    )
})

pattern = re.compile(
    r"BEGIN (?:RSA|OPENSSH|EC|ED25519) PRIVATE KEY|"
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"sk-[A-Za-z0-9]{20,}"
)
excluded_parts = {".git", "__pycache__", "external_baselines", ".venv", "venv"}
violations: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in excluded_parts for part in path.parts):
        continue
    if path.suffix in {".pyc", ".db", ".sqlite", ".sqlite3", ".jsonl"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    if pattern.search(text):
        violations.append(str(path.relative_to(ROOT)))

if violations:
    raise SystemExit("secret_scan_failed=" + ",".join(violations))
print("secret_scan=passed")
