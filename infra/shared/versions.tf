terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Bucket state tạo tay một lần (xem README). Truyền bằng:
  #   terraform init -backend-config="bucket=ccapi-tfstate-<PROJECT_ID>"
  backend "gcs" {
    prefix = "shared"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
