"""Read-only Docker inspection over GCE SSH via IAP.

Does not create, restart, resize or delete resources.
"""
import argparse
import json
import re
import subprocess
import shutil
import os
from pathlib import Path

from benchmark.io import utcnow, write_json


def main():
    parser = argparse.ArgumentParser()
    for field in ("project", "zone", "vm", "container", "instance-id"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/iaas_container_evidence.json"),
    )
    args = parser.parse_args()

    for value in (
        args.project,
        args.zone,
        args.vm,
        args.container,
        args.instance_id,
    ):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", value):
            raise ValueError("Invalid identifier")

    gcloud = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if not gcloud:
        raise RuntimeError("Google Cloud CLI not found in PATH")

    remote_command = (
        "sudo -n docker inspect "
        "--format '{{json .HostConfig}}' "
        + args.container
    )

    cmd = [
        gcloud,
        "compute", "ssh",
        args.vm,
        "--project", args.project,
        "--zone", args.zone,
        "--tunnel-through-iap",
        "--command", remote_command,
        "--quiet",
    ]

    if os.name == "nt" and gcloud.lower().endswith((".cmd", ".bat")):
        # shell=True handles quoted paths containing spaces in Windows .cmd files.
        result = subprocess.run(
            subprocess.list2cmdline(cmd),
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise RuntimeError(
            "Docker inspection failed.\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT: {result.stdout.strip()}\n"
            f"STDERR: {result.stderr.strip()}"
        )

    try:
        host = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Could not parse Docker inspect JSON.\n"
            f"Output: {result.stdout}"
        ) from exc

    nano = host.get("NanoCpus", 0)
    quota = host.get("CpuQuota", 0)
    period = host.get("CpuPeriod", 0)

    cpu_limit = (
        nano / 1e9
        if nano
        else quota / period
        if quota > 0 and period > 0
        else None
    )

    memory_bytes = host.get("Memory", 0)
    memory_swap_bytes = host.get("MemorySwap", 0)

    evidence = {
        "verified_at": utcnow(),
        "instance_id": args.instance_id,
        "container": args.container,
        "cpu_limit": cpu_limit,
        "memory_bytes": memory_bytes,
        "memory_swap_bytes": memory_swap_bytes,
        "memory_limit_gib": memory_bytes / (1024 ** 3),
        "source": "read-only sudo docker inspect over gcloud compute ssh via IAP",
        "worker_count": "verify application worker configuration separately",
    }

    write_json(args.output, evidence)

    print(json.dumps(evidence, indent=2))
    print(f"\nEvidence saved: {args.output}")


if __name__ == "__main__":
    main()
