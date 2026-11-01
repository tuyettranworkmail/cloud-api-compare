output "external_ip" {
  value = google_compute_address.ip.address
}

output "base_url" {
  value = "http://${google_compute_address.ip.address}"
}

output "ssh_command" {
  value = "gcloud compute ssh ${google_compute_instance.api.name} --zone ${var.zone} --project ${var.project_id} --tunnel-through-iap"
}

output "test_commands" {
  value = [
    "curl -i http://${google_compute_address.ip.address}/health",
    "curl -i http://${google_compute_address.ip.address}/items/item-000001",
    "curl -i \"http://${google_compute_address.ip.address}/compute?n=1000\"",
  ]
}
