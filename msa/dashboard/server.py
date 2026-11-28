"""architecture-service: live architecture and resilience console.

Runs inside the cluster and talks to the Kubernetes API with its own
ServiceAccount (see msa/deploy/base/architecture-rbac.yaml). The shop frontend
proxies /architecture to this service, so the console shares the shop's port.

Python standard library only. Every number comes from the Kubernetes API or
from reviews-service itself; nothing is simulated.

Local development without a cluster pod:
    kubectl proxy --port 8001
    set K8S_API=http://localhost:8001 && python msa\\dashboard\\server.py
"""
import json
import os
import queue
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SA = "/var/run/secrets/kubernetes.io/serviceaccount"
K8S_API = os.environ.get("K8S_API", "https://kubernetes.default.svc")
PORT = int(os.environ.get("PORT", "8090"))
REVIEWS_URL = os.environ.get("REVIEWS_URL", "http://reviews-service:8080")
HEAL_GRACE = float(os.environ.get("HEAL_GRACE_SECONDS", "8"))
HERE = os.path.dirname(os.path.abspath(__file__))


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


NS = os.environ.get("NS") or read(SA + "/namespace", "boutique-staging")
TOKEN = read(SA + "/token")
CTX = ssl.create_default_context(cafile=SA + "/ca.crt") if os.path.exists(SA + "/ca.crt") else None

# Workloads the console may touch. architecture-service itself is excluded on purpose.
SERVICES = [
    "frontend", "adservice", "cartservice", "checkoutservice", "currencyservice",
    "emailservice", "paymentservice", "productcatalogservice",
    "recommendationservice", "shippingservice", "redis-cart", "reviews-service",
    "loadgenerator",
]
DEFAULT_BASELINE = {s: 1 for s in SERVICES}
DEFAULT_BASELINE["frontend"] = 2  # two replicas so the console stays reachable while one is killed

lock = threading.Lock()
baseline = dict(DEFAULT_BASELINE)
autoheal = {"enabled": True}
heal_log = []          # recent self-healing actions
mismatch_since = {}    # service -> first time its replica count differed from baseline


# ---------------------------------------------------------------- Kubernetes
def k8s(method, path, body=None, content_type="application/json", timeout=10):
    headers = {"Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = content_type
    req = urllib.request.Request(K8S_API + path, data=data, method=method, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout, context=CTX)


def k8s_json(method, path, body=None, content_type="application/json"):
    try:
        with k8s(method, path, body, content_type) as r:
            return True, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.reason}: {e.read().decode(errors='replace')[:200]}"
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, str(e)


def parse_cpu(v):
    for suffix, div in (("n", 1_000_000), ("u", 1000), ("m", 1)):
        if v.endswith(suffix):
            return int(v[:-1]) / div
    return float(v) * 1000


def parse_mem(v):
    units = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024}
    for suffix, mult in units.items():
        if v.endswith(suffix):
            return int(v[:-2]) * mult
    return int(v) / 1048576


def pods_by_service():
    ok, res = k8s_json("GET", f"/api/v1/namespaces/{NS}/pods")
    if not ok:
        return False, res
    out = {}
    for pod in res["items"]:
        name = pod["metadata"].get("labels", {}).get("app")
        if name in SERVICES:
            out.setdefault(name, []).append(pod)
    return True, out


def usable(pod):
    return "deletionTimestamp" not in pod["metadata"] and pod["status"].get("phase") in ("Running", "Pending")


def scale(service, replicas):
    return k8s_json("PATCH", f"/apis/apps/v1/namespaces/{NS}/deployments/{service}/scale",
                    {"spec": {"replicas": int(replicas)}}, "application/merge-patch+json")


def kill_service(service):
    ok, pods = pods_by_service()
    if not ok:
        return False, pods
    victims = [p["metadata"]["name"] for p in pods.get(service, []) if "deletionTimestamp" not in p["metadata"]]
    for n in victims:
        k8s_json("DELETE", f"/api/v1/namespaces/{NS}/pods/{n}")
    return True, f"deleted {len(victims)} pod(s) of {service}"


def state():
    ok, pods = pods_by_service()
    if not ok:
        return {"cluster": False, "error": pods}
    usage = {}
    mok, m = k8s_json("GET", f"/apis/metrics.k8s.io/v1beta1/namespaces/{NS}/pods")
    if mok:
        for it in m.get("items", []):
            c = it.get("containers") or [{}]
            usage[it["metadata"]["name"]] = {
                "cpu_m": round(sum(parse_cpu(x["usage"]["cpu"]) for x in c), 1),
                "mem_mi": round(sum(parse_mem(x["usage"]["memory"]) for x in c), 1)}
    services = {}
    for name in SERVICES:
        plist = pods.get(name, [])
        entry = {"pods": [], "ready": 0, "total": 0}
        for pod in plist:
            st = pod["status"]
            cs = (st.get("containerStatuses") or [{}])[0]
            term = "deletionTimestamp" in pod["metadata"]
            waiting = (cs.get("state") or {}).get("waiting", {}).get("reason")
            phase = "Terminating" if term else (waiting or st.get("phase", "Unknown"))
            ready = bool(cs.get("ready")) and not term
            entry["total"] += 1
            entry["ready"] += 1 if ready else 0
            entry["pods"].append({"name": pod["metadata"]["name"], "phase": phase, "ready": ready,
                                  "restarts": cs.get("restartCount", 0), "started": st.get("startTime"),
                                  **usage.get(pod["metadata"]["name"], {})})
        services[name] = entry
    dok, dep = k8s_json("GET", f"/apis/apps/v1/namespaces/{NS}/deployments")
    if dok:
        for d in dep["items"]:
            if d["metadata"]["name"] in services:
                services[d["metadata"]["name"]]["desired"] = d["spec"].get("replicas", 0)
    eok, ev = k8s_json("GET", f"/api/v1/namespaces/{NS}/events")
    events = []
    if eok:
        items = sorted(ev["items"], key=lambda e: e.get("lastTimestamp") or e.get("eventTime") or e["metadata"]["creationTimestamp"])
        for e in items[-30:]:
            events.append({"time": e.get("lastTimestamp") or e.get("eventTime") or "",
                           "type": e.get("type"), "reason": e.get("reason"),
                           "object": e["involvedObject"].get("name"), "message": (e.get("message") or "")[:160]})
        events.reverse()
    with lock:
        return {"cluster": True, "namespace": NS, "metrics": mok, "services": services,
                "events": events, "baseline": dict(baseline), "autoheal": autoheal["enabled"],
                "heal_grace": HEAL_GRACE, "heal_log": list(heal_log[:15]), "now": time.time()}


# ---------------------------------------------------------------- self healing
def log_heal(msg):
    with lock:
        heal_log.insert(0, {"t": time.strftime("%H:%M:%S"), "msg": msg})
        del heal_log[40:]


def heal_loop():
    """Reconcile replica counts to the baseline. Deleted pods are already
    recreated by the Deployment controller; this loop also restores the replica
    COUNT when someone scales a service up, down or to zero."""
    while True:
        time.sleep(2)
        try:
            with lock:
                enabled = autoheal["enabled"]
                want = dict(baseline)
            ok, dep = k8s_json("GET", f"/apis/apps/v1/namespaces/{NS}/deployments")
            if not ok or not enabled:
                mismatch_since.clear()
                continue
            now = time.time()
            for d in dep["items"]:
                n = d["metadata"]["name"]
                if n not in want:
                    continue
                have = d["spec"].get("replicas", 0)
                if have == want[n]:
                    mismatch_since.pop(n, None)
                    continue
                first = mismatch_since.setdefault(n, now)
                if now - first >= HEAL_GRACE:
                    sok, _ = scale(n, want[n])
                    log_heal(f"{n}: replicas {have} -> {want[n]} (baseline restored)" if sok else f"{n}: restore failed")
                    mismatch_since.pop(n, None)
        except Exception as exc:  # keep the loop alive
            print("heal loop error:", exc, file=sys.stderr)


# ---------------------------------------------------------------- reviews-service
def reviews_call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(REVIEWS_URL + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=4) as r:
            return True, json.loads(r.read() or b"null")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, str(exc)


def reviews_info():
    ok, ver = reviews_call("/version")
    if not ok:
        return {"reachable": False, "error": ver}
    _, events = reviews_call("/events")
    events = events if isinstance(events, list) else []
    return {"reachable": True, "version": ver.get("version"), "event_count": len(events),
            "last_events": [{"seq": e["seq"], "type": e["type"], "created_at": e["created_at"]} for e in events[-6:]]}


# ---------------------------------------------------------------- live logs (SSE)
def stream_logs(handler, service):
    """Follow the logs of a service across pod restarts."""
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()

    def send(kind, text):
        handler.wfile.write(f"event: {kind}\ndata: {json.dumps(text)}\n\n".encode())
        handler.wfile.flush()

    last_status = None
    attached = None
    try:
        send("status", f"watching {service}")
        while True:
            ok, pods = pods_by_service()
            candidates = [p for p in pods.get(service, []) if usable(p)] if ok else []
            if not candidates:
                if last_status != "none":
                    send("status", "no running pod, waiting for Kubernetes to start one")
                    last_status = "none"
                time.sleep(1)
                continue
            pod = sorted(candidates, key=lambda p: p["metadata"]["creationTimestamp"])[-1]["metadata"]["name"]
            q = queue.Queue()

            def reader(p=pod):
                try:
                    qs = urllib.parse.urlencode({"follow": "true", "tailLines": 40})
                    with k8s("GET", f"/api/v1/namespaces/{NS}/pods/{p}/log?{qs}", timeout=3600) as r:
                        for raw in r:
                            q.put(("line", raw.decode(errors="replace").rstrip()))
                except urllib.error.HTTPError as e:
                    q.put(("wait", f"{p}: container not ready yet ({e.code})"))
                except Exception as e:  # stream ended or pod removed
                    q.put(("wait", None))
                q.put(("end", None))

            if attached != pod:
                send("status", f"attached to pod {pod}")
                attached = pod
                last_status = "attached"
            threading.Thread(target=reader, daemon=True).start()
            while True:
                try:
                    kind, text = q.get(timeout=15)
                except queue.Empty:
                    handler.wfile.write(b": keepalive\n\n")
                    handler.wfile.flush()
                    continue
                if kind == "line":
                    send("log", text)
                elif kind == "wait":
                    if text:
                        send("status", text)
                elif kind == "end":
                    send("status", f"log stream of {pod} ended, looking for the replacement pod")
                    attached = None
                    break
            time.sleep(1)
    except (BrokenPipeError, ConnectionResetError, OSError):
        return


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif url.path == "/api/state":
            self.send_json(state())
        elif url.path == "/api/reviews":
            self.send_json(reviews_info())
        elif url.path == "/api/logs":
            service = urllib.parse.parse_qs(url.query).get("service", [""])[0]
            if service not in SERVICES:
                return self.send_json({"error": "unknown service"}, 400)
            self.close_connection = True
            stream_logs(self, service)
        elif url.path == "/healthz":
            self.send_json({"ok": True})
        else:
            self.send_error(404)

    def origin_ok(self):
        origin = self.headers.get("Origin", "")
        if not origin:
            return True
        return urllib.parse.urlparse(origin).netloc == self.headers.get("Host", "")

    def do_POST(self):
        if not self.origin_ok():
            return self.send_json({"ok": False, "message": "bad origin"}, 403)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self.send_json({"ok": False, "message": "bad json"}, 400)
        service = body.get("service")
        p = self.path
        if p == "/api/chaos/kill" and service in SERVICES:
            ok, msg = kill_service(service)
        elif p == "/api/chaos/scale" and service in SERVICES and isinstance(body.get("replicas"), int) \
                and 0 <= body["replicas"] <= 5:
            ok, msg = scale(service, body["replicas"])
            msg = f"{service} scaled to {body['replicas']}" if ok else msg
        elif p == "/api/chaos/kill-all":
            n = 0
            for s in SERVICES:
                ok1, _ = kill_service(s)
                n += 1 if ok1 else 0
            ok, msg = True, f"deleted every pod of {n} services"
        elif p == "/api/baseline" and service in SERVICES and isinstance(body.get("replicas"), int) \
                and 0 <= body["replicas"] <= 5:
            with lock:
                baseline[service] = body["replicas"]
            ok, msg = True, f"baseline for {service} is now {body['replicas']}"
        elif p == "/api/baseline/reset":
            with lock:
                baseline.clear()
                baseline.update(DEFAULT_BASELINE)
            ok, msg = True, "baseline reset to defaults"
        elif p == "/api/autoheal" and isinstance(body.get("enabled"), bool):
            with lock:
                autoheal["enabled"] = body["enabled"]
            ok, msg = True, "auto-heal " + ("on" if body["enabled"] else "off")
        elif p == "/api/restore":
            ok, msg = True, "restoring"
            with lock:
                want = dict(baseline)
            for s, n in want.items():
                scale(s, n)
            log_heal("manual restore: all replica counts set to baseline")
            msg = "all services set to their baseline replica count"
        elif p == "/api/reviews/seed":
            ok, msg = reviews_call("/commands/reviews", "POST", {
                "product_id": "OLJCESPC7Z", "author": "architecture-console",
                "rating": 5, "title": "Live demo review", "body": "Created from the architecture console."})
            msg = "review stored as an event" if ok else msg
        elif p == "/api/reviews/rebuild":
            ok, r = reviews_call("/admin/rebuild-projection", "POST", {})
            msg = f"replayed {r['events_replayed']} events into {r['reviews']} reviews" if ok else r
        else:
            return self.send_json({"ok": False, "message": "unknown action"}, 400)
        self.send_json({"ok": ok, "message": msg})


if __name__ == "__main__":
    threading.Thread(target=heal_loop, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"architecture-service for namespace {NS} on :{PORT}", flush=True)
    srv.serve_forever()
