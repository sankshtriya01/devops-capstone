output "app_namespace" {
  value = kubernetes_namespace.app.metadata[0].name
}

output "monitoring_namespace" {
  value = kubernetes_namespace.monitoring.metadata[0].name
}

output "grafana_hint" {
  value = "Run: kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80"
}
