"""Package portable source and reviewable outputs; exclude environments/secrets."""
from __future__ import annotations

import zipfile
from pathlib import Path

from benchmark.io import file_hash, write_json


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "deliverables"
    output.mkdir(exist_ok=True)
    excluded = {".venv", ".tools", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "deliverables", "excel_previews"}
    target = output / "benchmark-cost-analysis.zip"
    files = [path for path in root.rglob("*") if path.is_file() and not any(part in excluded or part.endswith(".egg-info") for part in path.relative_to(root).parts) and path.name != ".env" and "private_runtime_config" not in path.name]
    # Never include REAL raw/ADC/tokens in a generic shareable source bundle.
    files = [p for p in files if not p.relative_to(root).as_posix().startswith(("results/raw/", "results/monitoring/")) and p.suffix not in {".pem", ".key"}]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, arcname=Path("benchmark-cost-analysis") / path.relative_to(root))
    write_json(output / "package_manifest.json", {"archive": target.name, "sha256": file_hash(target), "files": len(files), "bytes": target.stat().st_size, "excluded": sorted(excluded), "cloud_raw_included": False})
    print(target, target.stat().st_size)


if __name__ == "__main__":
    main()
