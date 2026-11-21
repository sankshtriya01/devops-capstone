output "prometheus_release" {
  value = helm_release.monitoring.name
}
