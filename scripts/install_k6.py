"""Install an official k6 release locally, verifying the release SHA256 file."""
from __future__ import annotations

import argparse
import hashlib
import io
import platform
import tarfile
import zipfile
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="latest")
    args = parser.parse_args()
    system = {"Windows": "windows", "Linux": "linux"}.get(platform.system())
    if system is None or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise SystemExit("Script hỗ trợ Windows/Linux amd64; cài thủ công theo Grafana cho nền tảng khác")
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        suffix = "latest" if args.version == "latest" else "tags/" + args.version
        release = client.get(f"https://api.github.com/repos/grafana/k6/releases/{suffix}")
        release.raise_for_status()
        data = release.json()
        extension = ".zip" if system == "windows" else ".tar.gz"
        filename = f'k6-{data["tag_name"]}-{system}-amd64{extension}'
        asset = next(item for item in data["assets"] if item["name"] == filename)
        checksum = next(item for item in data["assets"] if "checksum" in item["name"].lower() and item["name"].endswith(".txt"))
        response = client.get(asset["browser_download_url"])
        response.raise_for_status()
        digest_response = client.get(checksum["browser_download_url"])
        digest_response.raise_for_status()
        expected = next(line.split()[0] for line in digest_response.text.splitlines() if line.rstrip().endswith(filename))
        if hashlib.sha256(response.content).hexdigest() != expected:
            raise SystemExit("Checksum mismatch")
        directory = Path(".tools")
        directory.mkdir(exist_ok=True)
        target = directory / ("k6.exe" if system == "windows" else "k6")
        if system == "windows":
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                content = archive.read(next(name for name in archive.namelist() if name.endswith("/k6.exe")))
        else:
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
                member = next(item for item in archive.getmembers() if item.name.endswith("/k6") and item.isfile())
                content = archive.extractfile(member).read()
        target.write_bytes(content)
        target.chmod(0o755)
        print(f'Installed {data["tag_name"]}: {target} (SHA256 verified)')


if __name__ == "__main__":
    main()
