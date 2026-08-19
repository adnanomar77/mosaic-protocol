#!/usr/bin/env python3
"""Verify bibliography URLs without treating HTTP reachability as proof of content."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests


def extract_urls(bib_path: Path) -> list[tuple[str, str]]:
    text = bib_path.read_text(encoding="utf-8")
    entries = re.split(r"\n(?=@)", text)
    out: list[tuple[str, str]] = []
    for entry in entries:
        key_match = re.match(r"@\w+\{([^,]+),", entry)
        url_match = re.search(r"\burl\s*=\s*\{([^}]+)\}", entry)
        if key_match and url_match:
            out.append((key_match.group(1).strip(), url_match.group(1).strip()))
    return out


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    bib = root / "paper" / "ledger_submission" / "references.bib"
    out_path = root / "paper" / "reference_status.json"
    rows = []
    for key, url in extract_urls(bib):
        parsed = urlparse(url)
        row = {"key": key, "url": url, "scheme": parsed.scheme, "status": None, "final_url": None, "error": None}
        try:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=20,
                headers={"User-Agent": "MOSAIC-reference-audit/1.0"},
                stream=True,
            )
            row["status"] = response.status_code
            row["final_url"] = response.url
            restricted_publisher = (
                response.status_code == 403
                and (
                    response.url.startswith("https://epubs.siam.org/doi/")
                    or response.url.startswith("https://dl.acm.org/doi/")
                    or response.url.startswith("https://ieeexplore.ieee.org/")
                )
            )
            if restricted_publisher:
                row["status_class"] = "publisher_access_restricted"
            else:
                row["status_class"] = "ok" if response.status_code < 400 else "http_error"
            response.close()
        except requests.RequestException as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
    result = {"source": str(bib.relative_to(root)), "checked": len(rows), "results": rows}
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    acceptable = all(
        row["status"] and (row["status"] < 400 or row.get("status_class") == "publisher_access_restricted")
        for row in rows
    )
    return 0 if acceptable else 1


if __name__ == "__main__":
    sys.exit(main())
