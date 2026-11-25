# Viva notes

Answers match this repo; known gaps are stated openly.

1. **Why event sourcing for reviews?** Every change (`ReviewSubmitted`, `ReviewEdited`, `ReviewRemoved`) is stored as an immutable fact in `events`. That gives a free audit log (`GET /events`) and lets us rebuild derived data. It is mainly a learning goal; plain CRUD would be simpler (doc 07).
2. **Why SQLite?** No extra infrastructure, and the event append plus projection update fit in one local transaction. Cost: one writer, so one replica and no scale-out. Production would use a managed database.
3. **What is CQRS here?** Commands (`/commands/...`) validate, append an event and update `reviews_view`; queries (`/queries/...`) only read `reviews_view`. Separate models and URL space, but the same process and database file.
4. **Is it eventually consistent?** No. The projection is updated in the same transaction (`BEGIN IMMEDIATE` to `COMMIT` in `main.tx`), so a read right after a write sees it. It would become eventually consistent with an async projector or a separate read store.
5. **How do you rebuild the projection?** `POST /admin/rebuild-projection` drops `reviews_view` and replays all events in one transaction. A test compares the view before and after the rebuild.
6. **How is the event log protected?** SQLite triggers abort any UPDATE or DELETE on `events`, and a test checks that. It does not stop someone from replacing the DB file.
7. **How does rollback work?** `kubectl rollout undo deployment/reviews-service` returns to the previous ReplicaSet (image 1.0.0). Data survives because it lives on the PVC. `msa/scripts/rollout_demo.bat` shows it.
8. **Why `Recreate`, not `RollingUpdate`?** The SQLite file sits on a ReadWriteOnce PVC and must have one writer, so the old pod stops first. Consequence: brief downtime on update and rollback. The stateless Boutique services can roll without downtime.
9. **Why a separate namespace (`boutique-staging`)?** Isolation from other environments, its own ResourceQuota and LimitRange, and a clear target for the staging overlay. The dev overlay uses `boutique-dev`.
10. **What does Terraform manage?** Only the namespace, a ResourceQuota and a LimitRange via the kubernetes provider on local minikube. It does not deploy the apps (kustomize does); no cloud resources, no remote state.
11. **How does the contract protect consumers?** `msa/api/reviews-openapi.yaml` is the published contract; only additive changes within a version (doc 06). Upstream gRPC follows the same rules in `protos/demo.proto` (never reuse field numbers).
12. **How is data ownership enforced?** Each service owns its store (cart: Redis, catalog: JSON file in memory, reviews: SQLite) and others use its API. Reviews keeps only a loose `product_id` string and does not validate it against the catalog, an accepted coupling trade-off.
13. **Why is checkout your SEED(S) example?** `PlaceOrder` is a synchronous orchestration over cart, catalog, currency, shipping, payment and email. The proto has no refund RPC, so a failure after `Charge` has no compensation (read from source, not tested).
14. **What does CI check?** pytest, docker build of both image tags, `kubectl kustomize` of both overlays, `terraform fmt -check` and `validate`, and a kind-cluster deploy plus smoke test. None of it has run yet.
15. **What is NOT covered?** Cassandra and AWS setup, authentication, frontend integration, event versioning, multi-replica or zero-downtime reviews, real monitoring, and any execution evidence (see `EVIDENCE.md` Limitations).
