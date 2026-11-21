variable "kubeconfig_path" {
  description = "Path to your kubeconfig file"
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "Which cluster to use (see: kubectl config get-contexts)"
  type        = string
  default     = "docker-desktop"
}

variable "app_namespace" {
  description = "Namespace for the application"
  type        = string
  default     = "tasktracker"
}

variable "monitoring_namespace" {
  description = "Namespace for Prometheus, Grafana and Loki"
  type        = string
  default     = "monitoring"
}

variable "enable_gitops" {
  description = "Install Argo CD (GitOps). Set to false on a low-memory laptop."
  type        = bool
  default     = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password. Pass it with -var or TF_VAR_grafana_admin_password; do not commit it."
  type        = string
  sensitive   = true
}
