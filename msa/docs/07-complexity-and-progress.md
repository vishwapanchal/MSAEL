# 07 - Complexity and Progress (bonus)

## Counts you can verify

| Measure | Value | Source |
|---|---|---|
| Workloads in release manifest | 12 (10 app services + loadgenerator + redis-cart) | `release/kubernetes-manifests.yaml` |
| gRPC services in proto | 9 | `protos/demo.proto` |
| RPCs in proto | 15 | `protos/demo.proto` |
| Languages in baseline | 5 (Go, C#, Java, Node.js, Python) | `src/*` |
| Cart store implementations | 3 (Redis default, Spanner, AlloyDB) | `src/cartservice/src/cartstore` |
| Source service not in release manifest | 1 (shoppingassistantservice) | `src/shoppingassistantservice` |
| Our additions | 1 service, 3 event types, 3 command routes, 2 query routes, 4 ops routes | `msa/api/reviews-openapi.yaml` |

Checkout fan-out: one `PlaceOrder` calls 6 distinct services (cart, catalog, currency, shipping, payment, email), see doc 03.

## Complexity is in the edges
Every call is a latency and failure point. Checkout's synchronous chain means its availability is bounded by the availability of everything it calls (roughly the product of them).

## Measuring progress (no invented numbers)
- Milestone checklist: service builds in CI; deployed to `boutique-staging`; `/healthz` ok; commands and queries work; rollout 1.0.0 -> 1.1.0 -> rollback demonstrated; Terraform applies namespace, quota and limits.
- Delivery signals readable from the repo: pipeline pass/fail, commits and PRs.
- Operational signals to collect if monitoring is added (not claimed here): request latency, error rate, pod restarts.

## Complexity we chose to add
Event sourcing, CQRS and a stateful workload (PVC, Recreate). Justification: they are course learning goals; for plain CRUD reviews, state-based SQLite would be simpler.

## How this maps to the syllabus
Architecture evaluation, complexity management, delivery and operational metrics.

## Evidence in this repo
- `release/kubernetes-manifests.yaml`, `protos/demo.proto`
- `.github/workflows/msa-ci.yaml`, `msa/scripts/rollout_demo.bat`, `msa/iac/staging`
