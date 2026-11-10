variable "project_id" {
  description = "Existing GCP project ID."
  type        = string
}

variable "region" {
  description = "Same region as the IaaS/PaaS/FaaS APIs."
  type        = string
  default     = "asia-southeast1"
}

variable "zone" {
  type    = string
  default = "asia-southeast1-b"
  validation {
    condition     = startswith(var.zone, "${var.region}-")
    error_message = "The load generator zone must belong to the configured region."
  }
}

variable "vm_name" {
  type    = string
  default = "benchmark-loadgen"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-2"
}

variable "subnetwork_self_link" {
  description = "Existing subnet self_link in the target region; coordinate with the infrastructure owner."
  type        = string
}

variable "service_account_email" {
  description = "Existing dedicated service account with only necessary read/Invoker IAM roles."
  type        = string
}

variable "assign_external_ip" {
  description = "Enable an external egress IP only when the subnet has no Cloud NAT. Does not open ingress."
  type        = bool
  default     = false
}

variable "boot_disk_size_gb" {
  type    = number
  default = 30
  validation {
    condition     = var.boot_disk_size_gb >= 20
    error_message = "Boot disk must be at least 20 GB."
  }
}
