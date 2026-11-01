locals {
  labels = {
    project = "ccapi"
    owner   = "tran"
    model   = "iaas"
  }

  sa_email      = "${var.api_service_account_name}@${var.project_id}.iam.gserviceaccount.com"
  registry_host = "${var.region}-docker.pkg.dev"
  image         = "${local.registry_host}/${var.project_id}/ccapi/ccapi:${var.image_tag}"
}

# --- API cần bật thêm cho IaaS (compute đã bật ở infra/shared) ---
resource "google_project_service" "iap" {
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

# --- Mạng riêng cho VM ---
resource "google_compute_network" "vpc" {
  name                    = "ccapi-iaas-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "ccapi-iaas-subnet"
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = "10.10.0.0/24"
}

resource "google_compute_firewall" "http" {
  name          = "ccapi-iaas-allow-http"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  source_ranges = var.http_source_ranges
  target_tags   = ["ccapi-iaas"]

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }
}

# SSH chỉ qua IAP (dải 35.235.240.0/20) cộng thêm IP tùy chọn
resource "google_compute_firewall" "ssh" {
  name          = "ccapi-iaas-allow-ssh"
  network       = google_compute_network.vpc.name
  direction     = "INGRESS"
  source_ranges = concat(["35.235.240.0/20"], var.ssh_source_ranges)
  target_tags   = ["ccapi-iaas"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

# --- Quyền cho service account chạy trên VM ---
# (infra/shared đã cấp datastore.user và logging.logWriter)
resource "google_artifact_registry_repository_iam_member" "vm_pull" {
  project    = var.project_id
  location   = var.region
  repository = "ccapi"
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.sa_email}"
}

resource "google_project_iam_member" "vm_metrics" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${local.sa_email}"
}

# --- IP tĩnh để địa chỉ API ổn định giữa các lần khởi động lại ---
resource "google_compute_address" "ip" {
  name   = "ccapi-iaas-ip"
  region = var.region
}

# --- VM ---
resource "google_compute_instance" "api" {
  name         = "ccapi-iaas-api"
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["ccapi-iaas"]
  labels       = merge(local.labels, { git_sha = var.git_sha })

  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      # Ubuntu thường (không phải Container-Optimized OS) có chủ đích:
      # người vận hành phải tự vá OS và tự cài Docker, đúng bản chất IaaS cần đo.
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = 20
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id

    access_config {
      nat_ip = google_compute_address.ip.address
    }
  }

  service_account {
    email  = local.sa_email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh.tpl", {
    registry_host     = local.registry_host
    image             = local.image
    project_id        = var.project_id
    git_sha           = var.git_sha
    cpus              = var.container_cpus
    memory            = var.container_memory
    install_ops_agent = var.install_ops_agent
  })

  depends_on = [
    google_artifact_registry_repository_iam_member.vm_pull,
    google_project_iam_member.vm_metrics,
    google_compute_firewall.http,
    google_compute_firewall.ssh,
  ]
}
