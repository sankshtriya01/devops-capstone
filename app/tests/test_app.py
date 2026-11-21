import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import TASKS, app  # noqa: E402


@pytest.fixture()
def client():
    TASKS.clear()
    app.config["TESTING"] = True
    return app.test_client()


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_create_and_get_task(client):
    r = client.post("/tasks", json={"title": "write report"})
    assert r.status_code == 201
    task_id = r.get_json()["id"]
    r = client.get(f"/tasks/{task_id}")
    assert r.status_code == 200
    assert r.get_json()["title"] == "write report"


def test_create_requires_title(client):
    assert client.post("/tasks", json={}).status_code == 400
    assert client.post("/tasks", json={"title": "   "}).status_code == 400


def test_title_length_limit(client):
    assert client.post("/tasks", json={"title": "x" * 201}).status_code == 400


def test_update_task(client):
    task_id = client.post("/tasks", json={"title": "a"}).get_json()["id"]
    r = client.put(f"/tasks/{task_id}", json={"done": True})
    assert r.get_json()["done"] is True


def test_delete_task(client):
    task_id = client.post("/tasks", json={"title": "a"}).get_json()["id"]
    assert client.delete(f"/tasks/{task_id}").status_code == 204
    assert client.get(f"/tasks/{task_id}").status_code == 404


def test_missing_task_404(client):
    assert client.get("/tasks/nope").status_code == 404


def test_metrics_exposed(client):
    client.get("/health")
    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    assert "tasks_total" in body
    assert "app_info" in body


def test_crash_endpoint_disabled_by_default(client):
    assert client.get("/crash").status_code == 404
