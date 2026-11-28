# Presentation guide (about 15 minutes)

Order: problem, architecture, our service, operations, live demo, limits. Each section has what to say and what to show. Every claim below is backed by a file in this repository; open it if the professor asks.

## 1. Framing: "it is not just a website" (1 min)

- The shop is only the workload. The project is the platform around it: how 12 independently deployable services are built, deployed, changed and kept alive.
- Question to pose: what happens to the shop when one service dies, and how do teams change one service without coordinating with eleven others?
- Show: `msa/docs/01-architecture-overview.md` diagram.

## 2. Microservices and coordination cost (2 min)

- 12 workloads in five languages (Go, C#, Java, Node.js, Python) talk over gRPC. The contract is one file, `protos/demo.proto`: 9 services, 15 RPCs.
- Why it matters: the proto is the agreement between teams. A team can rewrite its service in another language as long as the contract holds.
- Three decisions and their trade-offs are in doc 01 (gRPC vs REST, one namespace vs many, polyglot vs one stack). Say the cost honestly: more moving parts, network failures, harder debugging.

## 3. Team Topologies (1 min)

- Stream-aligned teams per service group, a platform team (owns `run.bat`, kustomize, Terraform, CI), an enabling team. Show the service-to-team table in doc 02.

## 4. From requirements to services: SEED(S), event storming, DDD (2 min)

- We did not guess the boundaries. Actors and jobs-to-be-done (doc 03) gave us actions (commands) and queries. Event storming (doc 04) gave aggregates and bounded contexts.
- Why reviews is its own service: different change rate, different data shape (append-only history), different team, no dependency on checkout.
- Show: the sequence diagram for the reviews feature, and how its actions became the `/commands` routes and its queries the `/queries` routes.

## 5. Our service: event sourcing and CQRS (3 min)

- Instead of storing the current state of a review, we store what happened: `ReviewSubmitted`, `ReviewEdited`, `ReviewRemoved`. The events table is append-only; database triggers refuse UPDATE and DELETE.
- Writes go through commands. Reads go through a separate read model, `reviews_view`, built only from events. That is CQRS.
- Proof: `POST /admin/rebuild-projection` drops the read model and replays every event. Same result. Tests prove it (`pytest`: 18 passing).
- Data ownership: the service owns an embedded SQLite file on its own volume. No other service touches it. `product_id` is a plain string, a loose reference to the catalog, so there is no shared table and no call to another service. Doc 05 lists the data store of every service.
- Honest note: in this implementation the read model is updated in the same transaction as the event, so it is consistent immediately. In a split deployment, it would be eventually consistent. Say this before the professor asks.

## 6. Contract-first API (1 min)

- `msa/api/reviews-openapi.yaml` is generated from the code (OpenAPI 3.1), and the gRPC side is the proto file. Two open standards, one for each style.

## 7. DevOps, IaC, release (2 min)

- Terraform declares the namespace, ResourceQuota and LimitRange for `boutique-staging` (`msa/iac/staging`). Kustomize has a base and dev/staging overlays (`msa/deploy`).
- CI (`.github/workflows/msa-ci.yaml`): tests, image build, manifest rendering, Terraform checks, and a kind-cluster smoke test.
- Release and change: `run.bat demo` upgrades reviews-service from 1.0.0 to 1.1.0 with a rolling update, shows `/version`, then rolls back. Doc 06 explains backward-compatible API and proto evolution and what breaks consumers.
- Be honest: this service uses the `Recreate` strategy (one replica, one volume), so an update has a short downtime. A shared database would allow zero downtime, at the cost of ownership.

## 8. Live demo: the Architecture console (5 min)

Open http://localhost:8080 and click the Architecture button in the shop header. The console is served by the shop frontend on the same port, and runs inside the cluster as `architecture-service` with least-privilege access to this namespace only. Everything on screen comes from the Kubernetes API or from reviews-service; nothing is simulated.

1. Zoom into the topology. The paths are the real gRPC dependencies. Green means up. Point out the stacked cards and the pod dots: one dot per replica.
2. Run scenario 1, Self-healing. Narrate: the node turns red, the paths into it turn red, Kubernetes starts a replacement, and the resilience timeline shows the measured recovery time.
3. Click a service. A live log window opens. Kill that pod: the log shows the old pod ending and attaches to the replacement pod and its start-up logs.
4. Run scenario 2, Redundancy. The frontend has a baseline of 2 replicas. Kill one and the shop availability tile stays at 100%.
5. Run scenario 3, Data survives a crash. The event count is the same after reviews-service restarts, because its SQLite file lives on a volume.
6. Run scenario 4, then 5. Scale payments to 0 and watch auto-heal restore the baseline after 8 seconds. Then kill every pod: all 13 services return at their baseline counts (about 33 seconds when measured here).
7. Explain the baseline: each service has an editable replica count, and auto-heal keeps the cluster at it. Deleted pods are recreated by Kubernetes itself, auto-heal restores the replica count.

## 9. Limits and what is not covered (1 min)

- Not covered: Cassandra, AWS-specific setup.
- Not claimed: production hardening, authentication on the reviews API, per-request tracing.
- Run on a single local node, so "resilience" means pod-level recovery, not node or zone failure.
- The animated lines show that a path is available, not request volume.

## Questions to prepare for

See `msa/VIVA_NOTES.md` for 15 answers grounded in this repository. The most likely trap questions: why not a shared database, what happens to reviews if the pod dies, why is the read model rebuilt from events, what breaks if a field is removed from the proto.

## Evidence in this repo

`msa/dashboard/`, `msa/services/reviews-service/`, `msa/deploy/`, `msa/iac/staging/`, `msa/scripts/rollout_demo.bat`, `.github/workflows/msa-ci.yaml`.
