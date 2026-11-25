import pytest

PID = "OLJCESPC7Z"
GOOD = {"product_id": PID, "author": "ann", "rating": 5, "title": "Great", "body": "Loved it"}


def submit(client, **over):
    r = client.post("/commands/reviews", json={**GOOD, **over})
    assert r.status_code == 201, r.text
    return r.json()["review_id"]


def reviews(client, pid=PID):
    return client.get(f"/queries/products/{pid}/reviews").json()


def test_submit_creates_event_and_projection(client):
    rid = submit(client)
    evs = client.get("/events").json()
    assert [e["type"] for e in evs] == ["ReviewSubmitted"]
    assert evs[0]["review_id"] == rid and evs[0]["payload"]["rating"] == 5
    rows = reviews(client)
    assert len(rows) == 1 and rows[0]["review_id"] == rid and rows[0]["author"] == "ann"
    assert client.get(f"/queries/products/{PID}/rating-summary").json() == {
        "product_id": PID, "count": 1, "average": 5.0}


def test_edit(client):
    rid = submit(client)
    r = client.put(f"/commands/reviews/{rid}", json={"rating": 3, "title": "Meh", "body": "ok"})
    assert r.status_code == 200
    row = reviews(client)[0]
    assert row["rating"] == 3 and row["title"] == "Meh" and row["body"] == "ok"
    assert [e["type"] for e in client.get("/events").json()] == ["ReviewSubmitted", "ReviewEdited"]
    assert client.get(f"/queries/products/{PID}/rating-summary").json()["average"] == 3.0


def test_remove(client):
    rid = submit(client)
    assert client.delete(f"/commands/reviews/{rid}").status_code == 200
    assert reviews(client) == []
    assert client.get(f"/queries/products/{PID}/rating-summary").json()["count"] == 0
    types = [e["type"] for e in client.get("/events").json()]
    assert types == ["ReviewSubmitted", "ReviewRemoved"]  # history is kept
    assert client.delete(f"/commands/reviews/{rid}").status_code == 404


def test_summary_average(client):
    submit(client, rating=5)
    submit(client, rating=2)
    s = client.get(f"/queries/products/{PID}/rating-summary").json()
    assert s["count"] == 2 and s["average"] == 3.5


def test_rebuild_equals_live_projection(client):
    a = submit(client)
    submit(client, rating=1, product_id="66VCHSJNUP")
    c = submit(client, rating=4)
    client.put(f"/commands/reviews/{a}", json={"rating": 2, "title": "t", "body": "edited"})
    client.delete(f"/commands/reviews/{c}")
    before = (reviews(client), reviews(client, "66VCHSJNUP"))
    r = client.post("/admin/rebuild-projection")
    assert r.status_code == 200
    assert r.json() == {"events_replayed": 5, "reviews": 2}
    assert (reviews(client), reviews(client, "66VCHSJNUP")) == before


@pytest.mark.parametrize("over", [
    {"rating": 0}, {"rating": 6}, {"rating": "5"}, {"rating": 4.5},
    {"body": ""}, {"author": ""}, {"product_id": ""}, {"product_id": "bad id!"},
])
def test_submit_validation(client, over):
    assert client.post("/commands/reviews", json={**GOOD, **over}).status_code == 422
    assert client.get("/events").json() == []


def test_missing_field(client):
    bad = {k: v for k, v in GOOD.items() if k != "author"}
    assert client.post("/commands/reviews", json=bad).status_code == 422


def test_edit_validation(client):
    rid = submit(client)
    r = client.put(f"/commands/reviews/{rid}", json={"rating": 9, "body": "x"})
    assert r.status_code == 422
    assert len(client.get("/events").json()) == 1


def test_unknown_id_404(client):
    assert client.put("/commands/reviews/nope", json={"rating": 3, "body": "x"}).status_code == 404
    assert client.delete("/commands/reviews/nope").status_code == 404
    assert client.get("/events").json() == []


def test_events_append_only(client):
    submit(client)
    from app import events
    conn = events.connect()
    with pytest.raises(Exception):
        conn.execute("DELETE FROM events")
    with pytest.raises(Exception):
        conn.execute("UPDATE events SET type='x'")
    conn.close()


def test_ops(client, monkeypatch):
    assert client.get("/healthz").status_code == 200
    monkeypatch.setenv("APP_VERSION", "9.9.9")
    assert client.get("/version").json() == {"version": "9.9.9"}
