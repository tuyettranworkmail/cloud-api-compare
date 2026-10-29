#!/bin/bash
# Chạy mỗi lần VM khởi động. Chạy lại thủ công: sudo google_metadata_script_runner startup
# Log: /var/log/ccapi-startup.log
set -uo pipefail
exec > >(tee -a /var/log/ccapi-startup.log) 2>&1
echo "=== ccapi startup $(date -u +%FT%TZ) ==="

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io curl
  systemctl enable --now docker
fi

%{ if install_ops_agent ~}
if ! systemctl list-unit-files | grep -q google-cloud-ops-agent; then
  curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
  bash add-google-cloud-ops-agent-repo.sh --also-install || echo "Cai Ops Agent that bai"
fi
%{ endif ~}

# Đăng nhập Artifact Registry bằng token của service account gắn trên VM
TOKEN=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
echo "$TOKEN" | docker login -u oauth2accesstoken --password-stdin ${registry_host}

if docker pull ${image}; then
  docker rm -f ccapi 2>/dev/null || true
  docker run -d --name ccapi --restart=always \
    --cpus=${cpus} --memory=${memory} --memory-swap=${memory} \
    -p 80:8080 \
    -e MODEL=iaas -e STORE=firestore -e GCP_PROJECT=${project_id} \
    -e GIT_SHA=${git_sha} -e INSTANCE_ID=$(hostname) \
    ${image}
  echo "Da trien khai ${image}"
else
  echo "Khong pull duoc ${image}. Da push image len Artifact Registry chua?"
fi
