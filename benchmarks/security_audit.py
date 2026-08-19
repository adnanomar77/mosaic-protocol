"""Deterministic static audit for MOSAIC production gates."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "mosaic"
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {"pickle", "marshal", "dill"}


def audit_file(path: Path) -> list[dict]:
    findings: list[dict] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            findings.append({"severity": "critical", "file": str(path), "line": node.lineno, "finding": node.func.id})
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_MODULES:
                    findings.append({"severity": "critical", "file": str(path), "line": node.lineno, "finding": alias.name})
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "b64decode":
            has_validate = any(keyword.arg == "validate" for keyword in node.keywords)
            if not has_validate:
                findings.append({"severity": "medium", "file": str(path), "line": node.lineno, "finding": "base64 decode without validate=True"})
    return findings


def run() -> dict:
    findings: list[dict] = []
    files = sorted(PACKAGE.glob("*.py"))
    for path in files:
        findings.extend(audit_file(path))
    critical = [item for item in findings if item["severity"] == "critical"]
    return {
        "files_scanned": len(files),
        "findings": findings,
        "critical_count": len(critical),
        "passed": not critical,
        "scope": "AST static audit; not a substitute for independent cryptographic or penetration testing",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
