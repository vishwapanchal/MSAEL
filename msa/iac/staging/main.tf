resource "kubernetes_namespace" "staging" {
  metadata {
    name = var.namespace
    labels = {
      environment = "staging"
      managed-by  = "terraform"
    }
  }
}

resource "kubernetes_resource_quota" "staging" {
  metadata {
    name      = "staging-quota"
    namespace = kubernetes_namespace.staging.metadata[0].name
  }
  spec {
    hard = {
      "requests.cpu"    = var.quota_cpu_requests
      "requests.memory" = var.quota_memory_requests
      "limits.cpu"      = var.quota_cpu_limits
      "limits.memory"   = var.quota_memory_limits
      "pods"            = var.quota_pods
    }
  }
}

resource "kubernetes_limit_range" "staging" {
  metadata {
    name      = "staging-limits"
    namespace = kubernetes_namespace.staging.metadata[0].name
  }
  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "300m"
        memory = "256Mi"
      }
      default_request = {
        cpu    = "50m"
        memory = "64Mi"
      }
    }
  }
}
