output "namespace" {
  description = "Name of the staging namespace."
  value       = kubernetes_namespace.staging.metadata[0].name
}

output "resource_quota" {
  description = "Name of the ResourceQuota."
  value       = kubernetes_resource_quota.staging.metadata[0].name
}

output "limit_range" {
  description = "Name of the LimitRange."
  value       = kubernetes_limit_range.staging.metadata[0].name
}
