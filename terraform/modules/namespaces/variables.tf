variable "app_namespace" {
  description = "Namespace for the application"
  type        = string
}

variable "monitoring_namespace" {
  description = "Namespace for the monitoring tools"
  type        = string
}

variable "quota_requests_cpu" {
  type    = string
  default = "2"
}

variable "quota_requests_memory" {
  type    = string
  default = "4Gi"
}

variable "quota_limits_cpu" {
  type    = string
  default = "6"
}

variable "quota_limits_memory" {
  type    = string
  default = "6Gi"
}

variable "quota_pods" {
  type    = string
  default = "40"
}
