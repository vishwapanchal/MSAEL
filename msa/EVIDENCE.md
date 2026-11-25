# Evidence map

Status key: **verified** = actually executed or mechanically checked (grep/file reads) in this repo; **not verified here** = written and code-reviewed but never executed; **limitation** = known scope gap.

Nothing in `msa/`, `run.bat` or the workflow was executed: the authoring machine had no real Python, Docker, kubectl, minikube or Terraform. Only file reads, grep counts against upstream files and manual code review were done.

| # | Topic | Evidence path | Exact verify command | Status |
|---|---|---|---|---|
| 1 | Microservices overview | `msa/docs/01-architecture-overview.md`, `protos/demo.proto`, `release/kubernetes-manifests.yaml` | `grep -c "^kind: Deployment" release/kubernetes-manifests.yaml` (expect 12); `grep -c "^service " protos/demo.proto` (9); `grep -c "^\s*rpc " protos/demo.proto` (15) | verified (counts re-checked with grep) |
| 2 | Team Topologies | `msa/docs/02-team-topology.md` | open file; compare its service table with `grep "^  name:" release/kubernetes-manifests.yaml` | verified for the service list; the team split itself is a proposed model (limitation) |
| 3 | SEED(S) | `msa/docs/03-seeds-process.md`, `src/checkoutservice/main.go` | `grep -n "chargeCard\|shipOrder\|emptyUserCart\|sendOrderConfirmation" src/checkoutservice/main.go` | verified (call order read from source) |
| 4 | OpenAPI | `msa/api/reviews-openapi.yaml` (hand-written), `protos/demo.proto` | `cd msa/services/reviews-service && python export_openapi.py && git diff msa/api` (regenerates from FastAPI; expect only cosmetic diffs) | verified: `export_openapi.py` ran and regenerated the file from FastAPI (2026-11-25) |
| 5 | DDD / event storming | `msa/docs/04-event-storming-ddd.md` | `grep -n "ReviewSubmitted\|ReviewEdited\|ReviewRemoved" msa/services/reviews-service/app/events.py` | verified (event names match code) |
| 6 | Data ownership | `msa/docs/05-data-and-cqrs.md` (table covers all services) | `ls src/cartservice/src/cartstore`; `grep -n "ALLOYDB_CLUSTER_NAME" src/productcatalogservice/catalog_loader.go`; `grep -n "REDIS_ADDR" src/cartservice/src/Startup.cs` | verified for cart and catalog; "no store found" for the other services is a negative finding from reading, not an exhaustive proof |
| 7 | Event Sourcing + CQRS | `msa/services/reviews-service/app/{events,projection,main,models}.py`, `tests/test_reviews.py` | `cd msa/services/reviews-service && pip install -r requirements-dev.txt && pytest -q` | verified: 18 passed; smoke_test.py PASSED against local uvicorn (2026-11-25) |
| 8 | IaC + CI | `msa/iac/staging/*.tf`, `.github/workflows/msa-ci.yaml` | `cd msa/iac/staging && terraform fmt -check && terraform init -backend=false && terraform validate`; CI: push a branch and read the Actions run | partly verified: `terraform fmt -check` passes; `terraform init` failed twice (network reset downloading the kubernetes provider) so `validate` not verified; workflow never run on GitHub |
| 9 | Container workspace | `msa/services/reviews-service/Dockerfile`, `docker-compose.yml`, `msa/deploy/{base,overlays}`, `run.bat` | `docker compose -f msa/services/reviews-service/docker-compose.yml up --build`; `kubectl kustomize msa/deploy/overlays/staging`; `run.bat` | partly verified: `kubectl kustomize` renders staging and dev OK (namespace boutique-staging, image reviews-service:1.0.0); docker build, compose and `run.bat` not verified (Docker daemon not running) |
| 10 | Staging release / change | `msa/deploy/overlays/staging`, `msa/scripts/rollout_demo.bat`, `msa/docs/06-managing-change.md` | `msa\scripts\rollout_demo.bat`, then `kubectl -n boutique-staging rollout history deployment/reviews-service` | not verified here |
| - | `run.bat claude` fails gracefully without MASTER_PROMPT.md | `run.bat` labels `mode_claude`, `prompt_missing` | `run.bat claude` (expect "MASTER_PROMPT.md was not found", exit code 1) | not verified here (traced by reading: `where claude`, then `if not exist`) |

## Limitations

- Python tests, smoke test, OpenAPI export, `kubectl kustomize` and `terraform fmt` were executed on 2026-11-25. Docker build, minikube, `run.bat`, `rollout_demo.bat`, `terraform validate` and the GitHub Actions workflow were NOT executed (Docker Desktop daemon not started; provider download failed twice).
- Cassandra and AWS-specific setup are not covered. State is SQLite on a PVC; the cluster is local minikube; Terraform only manages namespace, ResourceQuota and LimitRange through the kubernetes provider (no cloud resources, no remote state).
- `reviews-service` is single-replica with `strategy: Recreate` (SQLite file on a ReadWriteOnce PVC), so updates and rollbacks cause a short outage. Zero-downtime rolling updates are not demonstrated for it.
- The existing frontend is not wired to `reviews-service`; the only link is the loose `product_id` string. No authentication, no event-schema versioning.
- Terraform is not wired to `run.bat`: if `run.bat` created the namespace first, run `terraform import` (see `msa/iac/staging/README.md`).
- The dev overlay targets namespace `boutique-dev`, which nothing creates automatically; CI only renders it.
- Team Topologies assignments are a proposal; the repo records no real teams.
- `msa/api/reviews-openapi.yaml` is hand-written and may differ cosmetically from FastAPI's generated output.
- Pinned versions (fastapi 0.115.6, pydantic 2.10.4, uvicorn 0.34.0, httpx 0.28.1) were chosen by compatibility reasoning, not by installing them.
