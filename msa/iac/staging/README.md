# Terraform: staging namespace

Declares the `boutique-staging` namespace, a ResourceQuota and a LimitRange
on a local minikube cluster (kubernetes provider `~> 2.30`). No cloud, no secrets.

```
cd msa/iac/staging
terraform init
terraform plan
terraform apply
```

Variables: `kubeconfig_path` (default `~/.kube/config`), `kube_context`
(default `minikube`), `namespace`, and the `quota_*` limits.

If `run.bat` already created the namespace, import it first:
`terraform import kubernetes_namespace.staging boutique-staging`.

CI checks: `terraform fmt -check` and `terraform validate`
(after `terraform init -backend=false`).
