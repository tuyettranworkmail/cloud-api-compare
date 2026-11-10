#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -d -m 0755 /etc/apt/keyrings
curl --fail --location --retry 3 --silent --show-error https://dl.k6.io/key.gpg | gpg --dearmor -o /etc/apt/keyrings/k6-archive-keyring.gpg
chmod 0644 /etc/apt/keyrings/k6-archive-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' > /etc/apt/sources.list.d/k6.list
apt-get update
apt-get install -y --no-install-recommends k6 python3 python3-venv git
mkdir -p /opt/benchmark
chmod 0755 /opt/benchmark
k6 version > /opt/benchmark/k6-version.txt
date -u +'%Y-%m-%dT%H:%M:%SZ' > /opt/benchmark/provisioned-at-utc.txt
