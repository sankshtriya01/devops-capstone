terraform {
  required_providers {
    helm = {
      source = "hashicorp/helm"
    }
  }
}

# Metrics (Prometheus), dashboards (Grafana) and alerts (Alertmanager).
resource "helm_release" "monitoring" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = var.namespace
  timeout    = 900

  set {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }
}

# Logging stack (Loki + Promtail) used for the Grafana log view.
resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  namespace  = var.namespace
  timeout    = 600

  set {
    name  = "promtail.enabled"
    value = "true"
  }

  # Grafana allows only one default data source (Prometheus already is one).
  set {
    name  = "loki.isDefault"
    value = "false"
  }
}

# Metrics server: lets the autoscaler see CPU use of the pods.
# The insecure-tls flag is only needed on local clusters (Docker Desktop, minikube).
resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/"
  chart      = "metrics-server"
  namespace  = "kube-system"
  timeout    = 300

  set {
    name  = "args[0]"
    value = "--kubelet-insecure-tls"
  }
}
