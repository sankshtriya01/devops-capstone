# Infrastructure as Code: prepares a Kubernetes cluster for the application.
# Works with any cluster your kubeconfig points to (Docker Desktop, minikube, EKS, GKE ...).
#
#   modules/namespaces : namespaces and the resource quota
#   modules/monitoring : Prometheus + Grafana, Loki, metrics-server
#   modules/gitops     : Argo CD
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

module "namespaces" {
  source                = "./modules/namespaces"
  app_namespace         = var.app_namespace
  monitoring_namespace  = var.monitoring_namespace
}

module "monitoring" {
  source                 = "./modules/monitoring"
  namespace              = module.namespaces.monitoring_namespace
  grafana_admin_password = var.grafana_admin_password
}

module "gitops" {
  count  = var.enable_gitops ? 1 : 0
  source = "./modules/gitops"
}

# The first version of this project kept everything in one file. These blocks tell
# Terraform that the existing resources simply moved into modules, so nothing is rebuilt.
moved {
  from = kubernetes_namespace.app
  to   = module.namespaces.kubernetes_namespace.app
}

moved {
  from = kubernetes_namespace.monitoring
  to   = module.namespaces.kubernetes_namespace.monitoring
}

moved {
  from = kubernetes_resource_quota.app
  to   = module.namespaces.kubernetes_resource_quota.app
}

moved {
  from = helm_release.monitoring
  to   = module.monitoring.helm_release.monitoring
}

moved {
  from = helm_release.loki
  to   = module.monitoring.helm_release.loki
}

moved {
  from = helm_release.metrics_server
  to   = module.monitoring.helm_release.metrics_server
}
