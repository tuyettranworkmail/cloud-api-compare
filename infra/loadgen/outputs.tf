output "vm_name" {
  value = google_compute_instance.loadgen.name
}

output "zone" {
  value = google_compute_instance.loadgen.zone
}

output "internal_ip" {
  value = google_compute_instance.loadgen.network_interface[0].network_ip
}

output "instance_id" {
  value = google_compute_instance.loadgen.instance_id
}

output "external_ip" {
  value = var.assign_external_ip ? google_compute_instance.loadgen.network_interface[0].access_config[0].nat_ip : null
}
