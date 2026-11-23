from fastapi.testclient import TestClient

from backend.app import app, tasks


def setup_function():
    tasks.clear()


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_complete_task():
    with TestClient(app) as client:
        created = client.post("/api/tasks", json={"title": "Validar despliegue"})
        assert created.status_code == 201
        assert created.json()["done"] is False
        completed = client.patch(f"/api/tasks/{created.json()['id']}")
    assert completed.status_code == 200
    assert completed.json()["done"] is True


def test_reject_empty_title():
    with TestClient(app) as client:
        response = client.post("/api/tasks", json={"title": ""})
    assert response.status_code == 422
