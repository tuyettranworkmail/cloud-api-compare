
terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    prefix = "paas"
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "image_tag" {
  type    = string
  default = "v1"
}

variable "git_sha" {
  type    = string
  default = "dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  image = "${var.region}-docker.pkg.dev/${var.project_id}/ccapi/ccapi:${var.image_tag}"
}

resource "google_cloud_run_v2_service" "paas" {
  name                = "ccapi-paas"
  location            = var.region
  deletion_protection = false

  template {
    service_account = "ccapi-api@${var.project_id}.iam.gserviceaccount.com"

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = local.image

      env {
        name  = "MODEL"
        value = "paas"
      }

      env {
        name  = "STORE"
        value = "firestore"
      }

      env {
        name  = "GIT_SHA"
        value = var.git_sha
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }
    }
  }
}

output "service_url" {
  value = google_cloud_run_v2_service.paas.uri
}
