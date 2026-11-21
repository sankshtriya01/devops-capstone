"""TaskTracker - sample application for the DevOps capstone.

A task manager with user accounts:
  Web pages : /login  /register  /  (task list)
  REST API  : /api/register  /api/login  /api/tasks ...
  Operations: /health (is the process alive)  /ready (is the database reachable)
              /metrics (Prometheus format)
Logs are written as JSON, one line per event, so log tools can parse them.
"""
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone

from flask import (Flask, Response, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
START_TIME = time.time()
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


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


def audit(event, **fields):
    log.info(event, extra={"extra_fields": fields})


# ---------- tiny in-memory metrics (Prometheus text format) ----------
_lock = threading.Lock()
_request_count = {}      # (method, path, status) -> count
_latency_sum = {}        # path -> total seconds
_latency_count = {}      # path -> number of requests

# ---------- database start-up ----------
_db_ready = False


def ensure_db():
    global _db_ready
    if not _db_ready:
        db.init(retries=1)
        _db_ready = True


NO_DB_PATHS = {"health", "metrics", "crash", "static"}


@app.before_request
def _start_timer():
    g.start = time.time()
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.before_request
def _check_database():
    if request.endpoint in NO_DB_PATHS or request.endpoint is None:
        return None
    try:
        ensure_db()
    except Exception as exc:  # database down or still starting
        log.error("database unavailable", extra={"extra_fields": {"error": str(exc)[:200]}})
        if request.path.startswith("/api/") or request.endpoint == "ready":
            return jsonify(error="database unavailable"), 503
        return render_template("error.html", code=503,
                               message="Service is starting. Please retry."), 503
    return None


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
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


# ---------- helpers ----------
def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    row = db.run("SELECT id, username FROM users WHERE id = ?", (uid,), fetch="one")
    return {"id": row[0], "username": row[1]} if row else None


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def csrf_ok():
    expected = session.get("csrf")
    sent = request.form.get("csrf", "")
    return bool(expected) and hmac.compare_digest(sent, expected)


def task_dict(row):
    return {"id": row[0], "title": row[1], "done": bool(row[2])}


def validate_credentials(username, password):
    if not USERNAME_RE.match(username):
        return "Username must be 3-30 letters, numbers or underscores."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


def create_user(username, password):
    """Returns (user_id, error)."""
    error = validate_credentials(username, password)
    if error:
        return None, error, 400
    existing = db.run("SELECT id FROM users WHERE username = ?", (username,), fetch="one")
    if existing:
        return None, "Username already taken.", 409
    user_id = str(uuid.uuid4())
    db.run("INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
           (user_id, username, generate_password_hash(password), now_iso()))
    audit("user_registered", user=username)
    return user_id, None, 201


def verify_login(username, password):
    row = db.run("SELECT id, password_hash FROM users WHERE username = ?",
                 (username,), fetch="one")
    ok = bool(row) and check_password_hash(row[1], password)
    audit("login", user=username, success=ok)
    return row[0] if ok else None


# ---------- operations endpoints ----------
@app.get("/health")
def health():
    return jsonify(status="ok", version=APP_VERSION,
                   uptime_seconds=round(time.time() - START_TIME, 1))


@app.get("/ready")
def ready():
    return jsonify(status="ready")


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
    try:
        ensure_db()
        total = db.run("SELECT COUNT(*) FROM tasks", fetch="one")[0]
        users = db.run("SELECT COUNT(*) FROM users", fetch="one")[0]
        lines += [
            "# HELP tasks_total Tasks currently stored",
            "# TYPE tasks_total gauge",
            f"tasks_total {total}",
            "# HELP users_total Registered users",
            "# TYPE users_total gauge",
            f"users_total {users}",
        ]
    except Exception:
        lines += ["# database metrics unavailable"]
    lines += [
        "# HELP app_info Application version",
        "# TYPE app_info gauge",
        f'app_info{{version="{APP_VERSION}"}} 1',
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


@app.get("/crash")
def crash():
    """Deliberate failure endpoint - used to demo alerts and rollback."""
    if os.getenv("ENABLE_CRASH_ENDPOINT", "false").lower() != "true":
        return jsonify(error="disabled"), 404
    return jsonify(error="simulated failure"), 500


# ---------- REST API ----------
def api_user():
    user = current_user()
    if not user:
        return None, (jsonify(error="login required"), 401)
    return user, None


@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    user_id, error, status = create_user(username, password)
    if error:
        return jsonify(error=error), status
    return jsonify(id=user_id, username=username), 201


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    user_id = verify_login(username, str(data.get("password", "")))
    if not user_id:
        return jsonify(error="invalid username or password"), 401
    session.clear()
    session["uid"] = user_id
    return jsonify(status="logged in")


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(status="logged out")


@app.post("/api/tasks")
def api_create_task():
    user, err = api_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    if not title:
        return jsonify(error="title is required"), 400
    if len(title) > 200:
        return jsonify(error="title too long (max 200)"), 400
    task_id = str(uuid.uuid4())
    db.run("INSERT INTO tasks (id, user_id, title, done, created_at) VALUES (?, ?, ?, 0, ?)",
           (task_id, user["id"], title, now_iso()))
    return jsonify(id=task_id, title=title, done=False), 201


@app.get("/api/tasks")
def api_list_tasks():
    user, err = api_user()
    if err:
        return err
    rows = db.run("SELECT id, title, done FROM tasks WHERE user_id = ? ORDER BY created_at",
                  (user["id"],), fetch="all")
    return jsonify([task_dict(r) for r in rows])


def find_task(task_id, user_id):
    return db.run("SELECT id, title, done FROM tasks WHERE id = ? AND user_id = ?",
                  (task_id, user_id), fetch="one")


@app.get("/api/tasks/<task_id>")
def api_get_task(task_id):
    user, err = api_user()
    if err:
        return err
    row = find_task(task_id, user["id"])
    if not row:
        return jsonify(error="not found"), 404
    return jsonify(task_dict(row))


@app.put("/api/tasks/<task_id>")
def api_update_task(task_id):
    user, err = api_user()
    if err:
        return err
    row = find_task(task_id, user["id"])
    if not row:
        return jsonify(error="not found"), 404
    data = request.get_json(silent=True) or {}
    title, done = row[1], row[2]
    if "title" in data:
        title = str(data["title"]).strip()
        if not title or len(title) > 200:
            return jsonify(error="title must be 1-200 characters"), 400
    if "done" in data:
        done = 1 if data["done"] else 0
    db.run("UPDATE tasks SET title = ?, done = ? WHERE id = ? AND user_id = ?",
           (title, done, task_id, user["id"]))
    return jsonify(id=task_id, title=title, done=bool(done))


@app.delete("/api/tasks/<task_id>")
def api_delete_task(task_id):
    user, err = api_user()
    if err:
        return err
    if not find_task(task_id, user["id"]):
        return jsonify(error="not found"), 404
    db.run("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"]))
    return "", 204


# ---------- web pages ----------
@app.get("/")
def index():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    rows = db.run("SELECT id, title, done FROM tasks WHERE user_id = ? ORDER BY created_at",
                  (user["id"],), fetch="all")
    return render_template("tasks.html", user=user, tasks=[task_dict(r) for r in rows])


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        if not csrf_ok():
            return render_template("register.html", error="Session expired. Try again."), 400
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_id, error, status = create_user(username, password)
        if error:
            return render_template("register.html", error=error), status
        flash("Account created. Please log in.")
        return redirect(url_for("login_page"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        if not csrf_ok():
            return render_template("login.html", error="Session expired. Try again."), 400
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user_id = verify_login(username, password)
        if not user_id:
            return render_template("login.html", error="Invalid username or password."), 401
        session.clear()
        session["uid"] = user_id
        return redirect(url_for("index"))
    return render_template("login.html")


@app.post("/logout")
def logout_page():
    if csrf_ok():
        session.clear()
    return redirect(url_for("login_page"))


@app.post("/ui/tasks")
def ui_add_task():
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if not csrf_ok():
        return render_template("error.html", code=400, message="Session expired."), 400
    title = request.form.get("title", "").strip()
    if not title or len(title) > 200:
        flash("Task title must be 1-200 characters.")
    else:
        db.run("INSERT INTO tasks (id, user_id, title, done, created_at) "
               "VALUES (?, ?, ?, 0, ?)", (str(uuid.uuid4()), user["id"], title, now_iso()))
    return redirect(url_for("index"))


@app.post("/ui/tasks/<task_id>/toggle")
def ui_toggle_task(task_id):
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if not csrf_ok():
        return render_template("error.html", code=400, message="Session expired."), 400
    row = find_task(task_id, user["id"])
    if row:
        db.run("UPDATE tasks SET done = ? WHERE id = ? AND user_id = ?",
               (0 if row[2] else 1, task_id, user["id"]))
    return redirect(url_for("index"))


@app.post("/ui/tasks/<task_id>/delete")
def ui_delete_task(task_id):
    user = current_user()
    if not user:
        return redirect(url_for("login_page"))
    if not csrf_ok():
        return render_template("error.html", code=400, message="Session expired."), 400
    db.run("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user["id"]))
    return redirect(url_for("index"))


# ---------- error handling ----------
@app.errorhandler(404)
def not_found(_):
    if request.path.startswith("/api/"):
        return jsonify(error="not found"), 404
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(405)
def method_not_allowed(_):
    if request.path.startswith("/api/"):
        return jsonify(error="method not allowed"), 405
    return render_template("error.html", code=405, message="Method not allowed."), 405


@app.errorhandler(500)
def server_error(_):
    if request.path.startswith("/api/"):
        return jsonify(error="internal server error"), 500
    return render_template("error.html", code=500, message="Something went wrong."), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))  # nosec B104
