"""Extract region-specific public Google pricing tables with evidence hashes.

No credential needed. This does not overwrite the reviewed catalog automatically.
Google's embedded table format may change: fail explicitly instead of guessing.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
from pathlib import Path

import httpx

from benchmark.io import file_hash, utcnow, write_json

URLS = {
    "run": "https://cloud.google.com/run/pricing",
    "vm": "https://cloud.google.com/products/compute/pricing/general-purpose",
    "firestore": "https://cloud.google.com/firestore/pricing",
    "disk": "https://cloud.google.com/compute/disks-image-pricing",
    "network": "https://cloud.google.com/vpc/network-pricing",
    "build": "https://cloud.google.com/build/pricing",
    "artifact": "https://cloud.google.com/artifact-registry/pricing",
    "observability": "https://cloud.google.com/stackdriver/pricing",
}


def extract_tables(text: str, region="Singapore (asia-southeast1)") -> list[list[str]]:
    tables = []

    def strings(value):
        if isinstance(value, str):
            yield re.sub("<[^>]+>", " ", html.unescape(value)).strip()
        elif isinstance(value, list):
            for entry in value:
                yield from strings(entry)

    def walk(value):
        if not isinstance(value, list):
            return
        if any(item == region for item in value if isinstance(item, str)) and not all(isinstance(item, str) for item in value):
            content = list(strings(value))
            if content not in tables:
                tables.append(content)
        else:
            for child in value:
                walk(child)

    for match in re.finditer(r"AF_initDataCallback\(", text):
        start = text.find("data:", match.end()) + 5
        if start < 5:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            walk(obj)
        except ValueError:
            continue
    return tables


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/sources"))
    parser.add_argument("--services", nargs="+", choices=URLS, default=list(URLS))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_file = args.output / "source_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        for service in args.services:
            response = client.get(URLS[service])
            response.raise_for_status()
            archive = args.output / f"{service}.html.gz"
            with gzip.open(archive, "wb") as stream:
                stream.write(response.content)
            tables = extract_tables(response.text)
            write_json(args.output / f"{service}_singapore_tables.json", tables)
            manifest[service] = {"url": URLS[service], "retrieved_at": utcnow(), "archive_sha256": file_hash(archive), "regional_tables": len(tables), "status": "TABLES_EXTRACTED_REVIEW_REQUIRED" if tables else "GLOBAL_TABLE_REVIEW_REQUIRED"}
            print(service, len(tables), flush=True)
    write_json(args.output / "source_manifest.json", manifest)


if __name__ == "__main__":
    main()
