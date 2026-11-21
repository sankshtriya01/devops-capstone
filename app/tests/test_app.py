import os
import re
import sys

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db  # noqa: E402
from main import app  # noqa: E402

PASSWORD = "correct-horse-1"


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    db.init(retries=1)
    db.reset_for_tests()
    return app.test_client()


def register_and_login(client, name="alice"):
    r = client.post("/api/register", json={"username": name, "password": PASSWORD})
    assert r.status_code == 201
    r = client.post("/api/login", json={"username": name, "password": PASSWORD})
    assert r.status_code == 200


def form_token(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf" value="([0-9a-f]+)"', html).group(1)


# ---- operations ----
def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_ready_checks_database(client):
    assert client.get("/ready").status_code == 200


def test_metrics_exposed(client):
    client.get("/health")
    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    assert "tasks_total" in body
    assert "users_total" in body
    assert "app_info" in body


def test_crash_endpoint_disabled_by_default(client):
    assert client.get("/crash").status_code == 404


# ---- accounts ----
def test_register_validation(client):
    short_name = {"username": "a", "password": PASSWORD}
    short_pass = {"username": "bob", "password": "short"}
    assert client.post("/api/register", json=short_name).status_code == 400
    assert client.post("/api/register", json=short_pass).status_code == 400


def test_duplicate_username_rejected(client):
    client.post("/api/register", json={"username": "bob", "password": PASSWORD})
    r = client.post("/api/register", json={"username": "bob", "password": PASSWORD})
    assert r.status_code == 409


def test_wrong_password_rejected(client):
    client.post("/api/register", json={"username": "bob", "password": PASSWORD})
    r = client.post("/api/login", json={"username": "bob", "password": "wrong-password"})
    assert r.status_code == 401


def test_password_is_stored_hashed(client):
    client.post("/api/register", json={"username": "bob", "password": PASSWORD})
    stored = db.run("SELECT password_hash FROM users", fetch="one")[0]
    assert PASSWORD not in stored


# ---- tasks API ----
def test_tasks_require_login(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "x"}).status_code == 401


def test_create_and_get_task(client):
    register_and_login(client)
    r = client.post("/api/tasks", json={"title": "write report"})
    assert r.status_code == 201
    task_id = r.get_json()["id"]
    r = client.get(f"/api/tasks/{task_id}")
    assert r.status_code == 200
    assert r.get_json()["title"] == "write report"
    assert len(client.get("/api/tasks").get_json()) == 1


def test_create_requires_title(client):
    register_and_login(client)
    assert client.post("/api/tasks", json={}).status_code == 400
    assert client.post("/api/tasks", json={"title": "   "}).status_code == 400


def test_title_length_limit(client):
    register_and_login(client)
    assert client.post("/api/tasks", json={"title": "x" * 201}).status_code == 400


def test_update_task(client):
    register_and_login(client)
    task_id = client.post("/api/tasks", json={"title": "a"}).get_json()["id"]
    r = client.put(f"/api/tasks/{task_id}", json={"done": True})
    assert r.get_json()["done"] is True


def test_delete_task(client):
    register_and_login(client)
    task_id = client.post("/api/tasks", json={"title": "a"}).get_json()["id"]
    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_missing_task_404(client):
    register_and_login(client)
    assert client.get("/api/tasks/nope").status_code == 404


def test_users_cannot_see_each_others_tasks(client):
    register_and_login(client, "alice")
    task_id = client.post("/api/tasks", json={"title": "private"}).get_json()["id"]
    other = app.test_client()
    register_and_login(other, "bob")
    assert other.get(f"/api/tasks/{task_id}").status_code == 404
    assert other.get("/api/tasks").get_json() == []


# ---- web pages ----
def test_home_redirects_to_login_when_logged_out(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_form_without_csrf_token_is_rejected(client):
    r = client.post("/login", data={"username": "a", "password": "b"})
    assert r.status_code == 400


def test_web_register_login_and_add_task(client):
    token = form_token(client, "/register")
    r = client.post("/register", data={"csrf": token, "username": "carol",
                                       "password": PASSWORD})
    assert r.status_code == 302
    token = form_token(client, "/login")
    r = client.post("/login", data={"csrf": token, "username": "carol", "password": PASSWORD})
    assert r.status_code == 302
    token = form_token(client, "/")
    client.post("/ui/tasks", data={"csrf": token, "title": "buy milk"})
    assert "buy milk" in client.get("/").get_data(as_text=True)


def test_unknown_page_shows_friendly_404(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "Page not found" in r.get_data(as_text=True)
