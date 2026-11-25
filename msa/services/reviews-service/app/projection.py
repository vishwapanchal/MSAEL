"""reviews_view read model, built only from events."""
import sqlite3

from . import events

VIEW_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS reviews_view (
        review_id  TEXT PRIMARY KEY,
        product_id TEXT NOT NULL,
        author     TEXT NOT NULL,
        rating     INTEGER NOT NULL,
        title      TEXT NOT NULL,
        body       TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_reviews_view_product ON reviews_view(product_id)",
]


def ensure(conn: sqlite3.Connection) -> None:
    """Create the view table if missing (safe inside or outside a transaction)."""
    for stmt in VIEW_STATEMENTS:
        conn.execute(stmt)


def apply(conn: sqlite3.Connection, ev: dict) -> None:
    """Apply one event to the projection."""
    p = ev["payload"]
    if ev["type"] == events.REVIEW_SUBMITTED:
        conn.execute(
            "INSERT OR REPLACE INTO reviews_view VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ev["review_id"], p["product_id"], p["author"], p["rating"], p["title"],
             p["body"], ev["created_at"], ev["created_at"]),
        )
    elif ev["type"] == events.REVIEW_EDITED:
        conn.execute(
            "UPDATE reviews_view SET rating=?, title=?, body=?, updated_at=? WHERE review_id=?",
            (p["rating"], p["title"], p["body"], ev["created_at"], ev["review_id"]),
        )
    elif ev["type"] == events.REVIEW_REMOVED:
        conn.execute("DELETE FROM reviews_view WHERE review_id=?", (ev["review_id"],))


def rebuild(conn: sqlite3.Connection) -> dict:
    """Drop the view and replay every event (single transaction)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DROP TABLE IF EXISTS reviews_view")
        ensure(conn)
        n = 0
        for ev in events.replay(conn):
            apply(conn, ev)
            n += 1
        reviews = conn.execute("SELECT COUNT(*) FROM reviews_view").fetchone()[0]
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"events_replayed": n, "reviews": reviews}


def exists(conn: sqlite3.Connection, review_id: str) -> bool:
    return conn.execute("SELECT 1 FROM reviews_view WHERE review_id=?", (review_id,)).fetchone() is not None


def list_reviews(conn: sqlite3.Connection, product_id: str) -> list:
    rows = conn.execute(
        "SELECT * FROM reviews_view WHERE product_id=? ORDER BY created_at, review_id", (product_id,))
    return [dict(r) for r in rows]


def rating_summary(conn: sqlite3.Connection, product_id: str) -> dict:
    row = conn.execute(
        "SELECT COUNT(*) AS c, AVG(rating) AS a FROM reviews_view WHERE product_id=?", (product_id,)).fetchone()
    return {"product_id": product_id, "count": row["c"],
            "average": round(row["a"], 2) if row["a"] is not None else 0.0}
