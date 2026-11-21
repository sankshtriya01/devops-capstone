variable "namespace" {
  description = "Namespace to install the monitoring tools into"
  type        = string
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}
