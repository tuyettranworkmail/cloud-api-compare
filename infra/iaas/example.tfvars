# Copy thành terraform.tfvars (file này bị .gitignore) rồi sửa.
project_id = "ccapi-tran-2026"
git_sha    = "dev" # đổi thành $(git rev-parse --short HEAD) của bản đã build
image_tag  = "v1"

# Khi đo chính thức, nên thu hẹp lại, ví dụ:
# http_source_ranges = ["<IP-cua-ban>/32", "<IP-VM-tai>/32"]
