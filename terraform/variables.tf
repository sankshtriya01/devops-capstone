variable "kubeconfig_path" {
  description = "Path to your kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Which cluster to use (see: kubectl config get-contexts)"
  type        = string
  default     = "minikube"
}

variable "grafana_admin_password" {
  description = "Grafana admin password. Pass it with -var or TF_VAR_grafana_admin_password; do not commit it."
  type        = string
  sensitive   = true
}
