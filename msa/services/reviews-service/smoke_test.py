"""Smoke test: python smoke_test.py http://localhost:8080  (stdlib only; exit 0 ok, 1 fail)."""
import json
import sys
import urllib.error
import urllib.request

PID = "OLJCESPC7Z"


def call(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("ok  -", msg)


def main(base):
    base = base.rstrip("/")
    s, _ = call(base, "GET", "/healthz")
    check(s == 200, "healthz")
    s, r = call(base, "POST", "/commands/reviews",
                {"product_id": PID, "author": "smoke", "rating": 5, "title": "t", "body": "first"})
    check(s == 201, "submit review")
    rid = r["review_id"]
    s, rows = call(base, "GET", f"/queries/products/{PID}/reviews")
    check(s == 200 and any(x["review_id"] == rid and x["rating"] == 5 for x in rows),
          "query shows review")
    s, _ = call(base, "PUT", f"/commands/reviews/{rid}", {"rating": 2, "title": "t2", "body": "edited"})
    check(s == 200, "edit review")
    s, rows = call(base, "GET", f"/queries/products/{PID}/reviews")
    check(next(x for x in rows if x["review_id"] == rid)["rating"] == 2, "edit visible in query")
    s, summ = call(base, "GET", f"/queries/products/{PID}/rating-summary")
    check(s == 200 and summ["count"] >= 1, "rating summary")
    s, _ = call(base, "DELETE", f"/commands/reviews/{rid}")
    check(s == 200, "remove review")
    s, before = call(base, "GET", f"/queries/products/{PID}/reviews")
    check(all(x["review_id"] != rid for x in before), "review gone from query")
    s, rb = call(base, "POST", "/admin/rebuild-projection")
    check(s == 200 and rb["events_replayed"] >= 3, "rebuild projection")
    s, after = call(base, "GET", f"/queries/products/{PID}/reviews")
    check(after == before, "query matches after rebuild")
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: smoke_test.py <base_url>")
        sys.exit(1)
    try:
        main(sys.argv[1])
    except Exception as e:  # noqa: BLE001
        print("SMOKE TEST FAILED:", repr(e))
        sys.exit(1)
