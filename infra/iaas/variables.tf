variable "project_id" {
  type        = string
  description = "ID project GCP"
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "zone" {
  type    = string
  default = "asia-southeast1-b"
}

variable "machine_type" {
  type        = string
  default     = "e2-standard-2"
  description = "Không dùng e2-micro/small/medium (lõi dùng chung, có burst, làm méo kết quả CPU)"
}

variable "image_tag" {
  type        = string
  default     = "v1"
  description = "Tag image trong Artifact Registry (repo ccapi, image ccapi)"
}

variable "git_sha" {
  type        = string
  default     = "dev"
  description = "Git SHA của bản build, ghi vào log và label để truy vết"
}

variable "container_cpus" {
  type        = string
  default     = "1"
  description = "Giới hạn CPU của container (cấu hình tương đương: 1 vCPU)"
}

variable "container_memory" {
  type        = string
  default     = "1g"
  description = "Giới hạn RAM của container (cấu hình tương đương: 1 GiB)"
}

variable "http_source_ranges" {
  type        = list(string)
  default     = ["0.0.0.0/0"]
  description = "Dải IP được gọi API (cổng 80). Nên thu hẹp lại còn IP của nhóm và VM tải khi đo."
}

variable "ssh_source_ranges" {
  type        = list(string)
  default     = []
  description = "IP bổ sung được SSH trực tiếp. Mặc định chỉ SSH qua IAP (35.235.240.0/20)."
}

variable "install_ops_agent" {
  type        = bool
  default     = true
  description = "Cài Ops Agent để có biểu đồ RAM, CPU trong Cloud Monitoring"
}

variable "api_service_account_name" {
  type        = string
  default     = "ccapi-api"
  description = "Tên service account tạo ở infra/shared"
}
