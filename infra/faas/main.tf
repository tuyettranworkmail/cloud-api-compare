
terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    prefix = "faas"
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "source_bucket" {
  type        = string
  description = "GCS bucket chua ma nguon FaaS"
}

variable "source_object" {
  type        = string
  description = "Ten file ZIP tren GCS"
}

variable "service_account_email" {
  type        = string
  description = "Service account duoc cap quyen"
}

variable "git_sha" {
  type    = string
  default = "dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_cloudfunctions2_function" "faas" {
  name        = "ccapi-faas"
  location    = var.region
  description = "CCAPI FaaS - Cloud Run functions"

  build_config {
    runtime     = "python312"
    entry_point = "ccapi"

    source {
      storage_source {
        bucket = var.source_bucket
        object = var.source_object
      }
    }
  }

  service_config {
    available_cpu    = "1"
    available_memory = "1Gi"
    timeout_seconds  = 60

    min_instance_count = 0
    max_instance_count = 10

    environment_variables = {
      MODEL   = "faas"
      STORE   = "firestore"
      GIT_SHA = var.git_sha
    }

    service_account_email = var.service_account_email
  }
}

output "function_url" {
  value = google_cloudfunctions2_function.faas.service_config[0].uri
}
