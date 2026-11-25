variable "kubeconfig_path" {
  description = "Path to the kubeconfig file."
  type        = string
  default     = "~/.kube/config"
}

variable "kube_context" {
  description = "kubeconfig context to use."
  type        = string
  default     = "minikube"
}

variable "namespace" {
  description = "Namespace for the staging environment."
  type        = string
  default     = "boutique-staging"
}

variable "quota_cpu_requests" {
  description = "Total CPU requests allowed in the namespace."
  type        = string
  default     = "4"
}

variable "quota_memory_requests" {
  description = "Total memory requests allowed in the namespace."
  type        = string
  default     = "4Gi"
}

variable "quota_cpu_limits" {
  description = "Total CPU limits allowed in the namespace."
  type        = string
  default     = "8"
}

variable "quota_memory_limits" {
  description = "Total memory limits allowed in the namespace."
  type        = string
  default     = "8Gi"
}

variable "quota_pods" {
  description = "Maximum number of pods in the namespace."
  type        = string
  default     = "40"
}
