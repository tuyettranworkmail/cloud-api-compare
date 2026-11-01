"""Read-only Docker inspection over an existing GCE SSH connection.

Does not create, restart, resize or delete resources. gcloud SSH must already work.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from benchmark.io import utcnow, write_json


def main():
    parser = argparse.ArgumentParser()
    for field in ("project", "zone", "vm", "container", "instance-id"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--output", type=Path, default=Path("results/iaas_container_evidence.json"))
    args = parser.parse_args()
    for value in (args.project, args.zone, args.vm, args.container, args.instance_id):
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", value):
            raise ValueError("Identifier không hợp lệ")
    command = "docker inspect --format '{{json .HostConfig}}' " + args.container
    result = subprocess.run(["gcloud", "compute", "ssh", args.vm, "--project", args.project, "--zone", args.zone, "--command", command, "--quiet"], check=True, capture_output=True, text=True)
    host = json.loads(result.stdout)
    nano, quota, period = host.get("NanoCpus", 0), host.get("CpuQuota", 0), host.get("CpuPeriod", 0)
    limit = nano / 1e9 if nano else quota / period if quota > 0 and period > 0 else None
    write_json(args.output, {"verified_at": utcnow(), "instance_id": args.instance_id, "container": args.container, "cpu_limit": limit, "memory_bytes": host.get("Memory", 0), "source": "read-only docker inspect over gcloud compute ssh", "worker_count": "verify application worker configuration separately"})
    print(args.output)


if __name__ == "__main__":
    main()
