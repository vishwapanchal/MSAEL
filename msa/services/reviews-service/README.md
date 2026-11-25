# reviews-service

Product reviews with CQRS + event sourcing. FastAPI, embedded SQLite (`$DATA_DIR/reviews.db`, default `/data`), port 8080.
`product_id` is a loose string reference (e.g. `OLJCESPC7Z` from `src/productcatalogservice/products.json`); it is not validated.

- Commands (validate, append event, update projection; one transaction):
  `POST /commands/reviews`, `PUT /commands/reviews/{id}`, `DELETE /commands/reviews/{id}`
- Queries (read `reviews_view`, built only from events):
  `GET /queries/products/{pid}/reviews`, `GET /queries/products/{pid}/rating-summary`
- Ops: `GET /healthz`, `GET /version`, `GET /events` (audit log), `POST /admin/rebuild-projection`
- Events (append-only table `events`): `ReviewSubmitted`, `ReviewEdited`, `ReviewRemoved`.

## Run (from this directory, Windows PowerShell)

    py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1
    pip install -r requirements-dev.txt
    pytest
    $env:DATA_DIR="$PWD\data"; uvicorn app.main:app --port 8080
    python smoke_test.py http://localhost:8080
    python export_openapi.py        # writes ../../api/reviews-openapi.yaml

Docker: `docker compose up --build` (named volume `reviews-data`); set a version with `--build-arg APP_VERSION=1.2.3`.
