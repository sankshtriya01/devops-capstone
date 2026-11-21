# Infrastructure as Code: prepares the Kubernetes cluster for the app.
# Works with any cluster your kubeconfig points to (minikube, kind, EKS, GKE ...).
terraform {
  required_version = ">= 1.6"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.33"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.15"
    }
  }
}

provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}

provider "helm" {
  kubernetes {
    config_path    = var.kubeconfig_path
    config_context = var.kube_context
  }
}

resource "kubernetes_namespace" "app" {
  metadata {
    name = "tasktracker"
    labels = {
      "pod-security.kubernetes.io/enforce" = "restricted"
    }
  }
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

# Stops the app from using more than its fair share of the cluster.
resource "kubernetes_resource_quota" "app" {
  metadata {
    name      = "app-quota"
    namespace = kubernetes_namespace.app.metadata[0].name
  }
  spec {
    hard = {
      "requests.cpu"    = "2"
      "requests.memory" = "2Gi"
      "limits.cpu"      = "4"
      "limits.memory"   = "4Gi"
      "pods"            = "30"
    }
  }
}

# Monitoring stack (Prometheus + Grafana + alert manager) installed automatically.
resource "helm_release" "monitoring" {
  name       = "kube-prometheus-stack"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  timeout    = 900

  set {
    name  = "grafana.adminPassword"
    value = var.grafana_admin_password
  }
}

# Logging stack (Loki + Promtail).
resource "helm_release" "loki" {
  name       = "loki"
  repository = "https://grafana.github.io/helm-charts"
  chart      = "loki-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  timeout    = 600

  set {
    name  = "promtail.enabled"
    value = "true"
  }
}
