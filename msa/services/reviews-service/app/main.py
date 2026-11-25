"""reviews-service: CQRS + event sourcing over embedded SQLite."""
import os
import uuid
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException

from . import events, projection
from .models import (CommandResult, EventOut, Health, RatingSummary, RebuildResult,
                     Review, ReviewCreate, ReviewEdit, Version)

app = FastAPI(title="reviews-service", version="1.0.0",
              description="Product reviews: event-sourced commands, projected queries.")


@contextmanager
def tx():
    """Connection with one write transaction: commit on success, rollback on error."""
    conn = events.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            projection.ensure(conn)
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


@contextmanager
def reader():
    conn = events.connect()
    try:
        projection.ensure(conn)
        yield conn
    finally:
        conn.close()


# ---- commands -------------------------------------------------------------

@app.post("/commands/reviews", status_code=201, response_model=CommandResult, tags=["commands"])
def submit_review(cmd: ReviewCreate):
    review_id = uuid.uuid4().hex
    with tx() as conn:
        ev = events.append(conn, review_id, events.REVIEW_SUBMITTED, cmd.model_dump())
        projection.apply(conn, ev)
    return {"review_id": review_id, "seq": ev["seq"]}


@app.put("/commands/reviews/{review_id}", response_model=CommandResult, tags=["commands"])
def edit_review(review_id: str, cmd: ReviewEdit):
    with tx() as conn:
        if not projection.exists(conn, review_id):
            raise HTTPException(status_code=404, detail="review not found")
        ev = events.append(conn, review_id, events.REVIEW_EDITED, cmd.model_dump())
        projection.apply(conn, ev)
    return {"review_id": review_id, "seq": ev["seq"]}


@app.delete("/commands/reviews/{review_id}", response_model=CommandResult, tags=["commands"])
def remove_review(review_id: str):
    with tx() as conn:
        if not projection.exists(conn, review_id):
            raise HTTPException(status_code=404, detail="review not found")
        ev = events.append(conn, review_id, events.REVIEW_REMOVED, {})
        projection.apply(conn, ev)
    return {"review_id": review_id, "seq": ev["seq"]}


# ---- queries --------------------------------------------------------------

@app.get("/queries/products/{product_id}/reviews", response_model=list[Review], tags=["queries"])
def product_reviews(product_id: str):
    with reader() as conn:
        return projection.list_reviews(conn, product_id)


@app.get("/queries/products/{product_id}/rating-summary", response_model=RatingSummary,
         tags=["queries"])
def product_rating_summary(product_id: str):
    with reader() as conn:
        return projection.rating_summary(conn, product_id)


# ---- ops ------------------------------------------------------------------

@app.get("/healthz", response_model=Health, tags=["ops"])
def healthz():
    with reader() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/version", response_model=Version, tags=["ops"])
def version():
    return {"version": os.environ.get("APP_VERSION", "1.0.0")}


@app.get("/events", response_model=list[EventOut], tags=["ops"])
def audit_log():
    with reader() as conn:
        return list(events.replay(conn))


@app.post("/admin/rebuild-projection", response_model=RebuildResult, tags=["ops"])
def rebuild_projection():
    conn = events.connect()
    try:
        return projection.rebuild(conn)
    finally:
        conn.close()
