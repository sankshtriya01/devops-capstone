output "app_namespace" {
  description = "Namespace where the application runs"
  value       = module.namespaces.app_namespace
}

output "monitoring_namespace" {
  description = "Namespace of the monitoring tools"
  value       = module.namespaces.monitoring_namespace
}

output "grafana_hint" {
  description = "How to open Grafana"
  value       = "Run: kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80"
}

output "argocd_hint" {
  description = "How to open Argo CD"
  value       = var.enable_gitops ? "Run: kubectl -n argocd port-forward svc/argocd-server 8443:443" : "GitOps disabled"
}
