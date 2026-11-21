"""TaskTracker API - the sample application for the DevOps capstone.

A small REST service for managing tasks. It exposes:
  /health   - liveness/readiness check (used by Kubernetes)
  /metrics  - Prometheus-format metrics (used by monitoring)
  /tasks    - the actual business API
Logs are written as JSON, one line per event, so Loki can parse them.
"""
import json
import logging
import os
import threading
import time
import uuid

from flask import Flask, Response, g, jsonify, request

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
START_TIME = time.time()

app = Flask(__name__)


# ---------- structured JSON logging ----------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "msg": record.getMessage(),
            "version": APP_VERSION,
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            entry.update(extra)
        return json.dumps(entry)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
log = logging.getLogger("tasktracker")
log.setLevel(logging.INFO)
log.handlers = [handler]
log.propagate = False

# ---------- tiny in-memory metrics (Prometheus text format) ----------
_lock = threading.Lock()
_request_count = {}      # (method, path, status) -> count
_latency_sum = {}        # path -> total seconds
_latency_count = {}      # path -> number of requests

# ---------- in-memory data store ----------
TASKS = {}


@app.before_request
def _start_timer():
    g.start = time.time()
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def _record(resp):
    elapsed = time.time() - g.start
    path = request.url_rule.rule if request.url_rule else "unmatched"
    with _lock:
        key = (request.method, path, resp.status_code)
        _request_count[key] = _request_count.get(key, 0) + 1
        _latency_sum[path] = _latency_sum.get(path, 0.0) + elapsed
        _latency_count[path] = _latency_count.get(path, 0) + 1
    log.info(
        "request",
        extra={"extra_fields": {
            "request_id": g.request_id,
            "method": request.method,
            "path": request.path,
            "status": resp.status_code,
            "duration_ms": round(elapsed * 1000, 2),
        }},
    )
    resp.headers["X-Request-ID"] = g.request_id
    return resp


# ---------- endpoints ----------
@app.get("/health")
def health():
    return jsonify(status="ok", version=APP_VERSION,
                   uptime_seconds=round(time.time() - START_TIME, 1))


@app.get("/metrics")
def metrics():
    lines = [
        "# HELP http_requests_total Total HTTP requests",
        "# TYPE http_requests_total counter",
    ]
    with _lock:
        for (method, path, status), n in sorted(_request_count.items()):
            lines.append(
                f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {n}')
        lines += [
            "# HELP http_request_duration_seconds_sum Total time spent handling requests",
            "# TYPE http_request_duration_seconds_sum counter",
        ]
        for path, total in sorted(_latency_sum.items()):
            lines.append(f'http_request_duration_seconds_sum{{path="{path}"}} {total:.6f}')
        lines += [
            "# HELP http_request_duration_seconds_count Number of timed requests",
            "# TYPE http_request_duration_seconds_count counter",
        ]
        for path, n in sorted(_latency_count.items()):
            lines.append(f'http_request_duration_seconds_count{{path="{path}"}} {n}')
    lines += [
        "# HELP tasks_total Tasks currently stored",
        "# TYPE tasks_total gauge",
        f"tasks_total {len(TASKS)}",
        "# HELP app_info Application version",
        "# TYPE app_info gauge",
        f'app_info{{version="{APP_VERSION}"}} 1',
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify(error="title is required"), 400
    if len(title) > 200:
        return jsonify(error="title too long (max 200)"), 400
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"id": task_id, "title": title, "done": False}
    return jsonify(TASKS[task_id]), 201


@app.get("/tasks")
def list_tasks():
    return jsonify(list(TASKS.values()))


@app.get("/tasks/<task_id>")
def get_task(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify(error="not found"), 404
    return jsonify(task)


@app.put("/tasks/<task_id>")
def update_task(task_id):
    task = TASKS.get(task_id)
    if not task:
        return jsonify(error="not found"), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = str(data["title"]).strip()
        if not title:
            return jsonify(error="title cannot be empty"), 400
        task["title"] = title
    if "done" in data:
        task["done"] = bool(data["done"])
    return jsonify(task)


@app.delete("/tasks/<task_id>")
def delete_task(task_id):
    if task_id not in TASKS:
        return jsonify(error="not found"), 404
    del TASKS[task_id]
    return "", 204


@app.get("/crash")
def crash():
    """Deliberate failure endpoint - used to demo alerts and rollback."""
    if os.getenv("ENABLE_CRASH_ENDPOINT", "false").lower() != "true":
        return jsonify(error="disabled"), 404
    return jsonify(error="simulated failure"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))  # nosec B104
