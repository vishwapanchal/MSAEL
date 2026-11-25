"""Append-only event store: append + read/replay."""
import json
import os
import sqlite3
from datetime import datetime, timezone

REVIEW_SUBMITTED = "ReviewSubmitted"
REVIEW_EDITED = "ReviewEdited"
REVIEW_REMOVED = "ReviewRemoved"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id    TEXT NOT NULL,
    type         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events
BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events
BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
"""


def db_path() -> str:
    return os.path.join(os.environ.get("DATA_DIR", "/data"), "reviews.db")


def connect() -> sqlite3.Connection:
    """New connection in autocommit mode; callers use explicit BEGIN/COMMIT."""
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def append(conn: sqlite3.Connection, review_id: str, type_: str, payload: dict) -> dict:
    """Insert an event and return it as a dict (caller owns the transaction)."""
    created_at = now()
    cur = conn.execute(
        "INSERT INTO events (review_id, type, payload_json, created_at) VALUES (?, ?, ?, ?)",
        (review_id, type_, json.dumps(payload, sort_keys=True), created_at),
    )
    return {"seq": cur.lastrowid, "review_id": review_id, "type": type_,
            "payload": payload, "created_at": created_at}


def row_to_event(row: sqlite3.Row) -> dict:
    return {"seq": row["seq"], "review_id": row["review_id"], "type": row["type"],
            "payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}


def replay(conn: sqlite3.Connection):
    """Yield all events in order."""
    for row in conn.execute("SELECT * FROM events ORDER BY seq").fetchall():
        yield row_to_event(row)
