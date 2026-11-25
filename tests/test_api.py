from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
import pytest

from backend import app as backend_app

app = backend_app.app
tasks = backend_app.tasks


def setup_function():
    tasks.clear()
    backend_app.next_id = 1


@pytest.fixture(autouse=True)
def isolated_inventory_database(tmp_path, monkeypatch):
    monkeypatch.setattr(backend_app, "DATABASE_PATH", tmp_path / "inventory.db")
    monkeypatch.setenv("INVENTORY_ADMIN_USER", "test-admin")
    monkeypatch.setenv("INVENTORY_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("INVENTORY_TOKEN_SECRET", "test-secret-key-for-api-tests")


def inventory_headers(client):
    response = client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_rejects_bad_credentials_and_protects_inventory():
    with TestClient(app) as client:
        denied = client.post("/api/auth/login", json={"username": "test-admin", "password": "wrong"})
        protected = client.get("/api/inventory")
        logged_in = client.post("/api/auth/login", json={"username": "test-admin", "password": "test-password"})
        authorized = client.get("/api/inventory", headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"})
    assert denied.status_code == 401
    assert protected.status_code == 401
    assert authorized.status_code == 200


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


def test_task_title_is_trimmed_and_listed():
    with TestClient(app) as client:
        created = client.post("/api/tasks", json={"title": "  revisar salud  "})
        listed = client.get("/api/tasks")
    assert created.status_code == 201
    assert created.json()["title"] == "revisar salud"
    assert listed.json() == [created.json()]


def test_reject_title_longer_than_limit():
    with TestClient(app) as client:
        response = client.post("/api/tasks", json={"title": "x" * 121})
    assert response.status_code == 422


def test_complete_unknown_task_returns_not_found():
    with TestClient(app) as client:
        response = client.patch("/api/tasks/999")
    assert response.status_code == 404


def test_inventory_create_list_and_summary():
    payload = {
        "sku": "TOOL-001", "name": " Taladro inalámbrico ", "category": "Herramientas",
        "quantity": 4, "min_stock": 5, "unit_price": 1200.5, "location": "Estante A-1"
    }
    with TestClient(app) as client:
        headers = inventory_headers(client)
        created = client.post("/api/inventory", json=payload, headers=headers)
        listed = client.get("/api/inventory", headers=headers)
        summary = client.get("/api/inventory/summary", headers=headers)
    assert created.status_code == 201
    assert created.json()["name"] == "Taladro inalámbrico"
    assert listed.json() == [created.json()]
    assert summary.json() == {"products": 1, "units": 4, "out_of_stock": 0, "low_stock": 1, "inventory_value": 4802.0}


def test_inventory_filters_by_search_category_and_stock():
    with TestClient(app) as client:
        headers = inventory_headers(client)
        client.post("/api/inventory", json={"sku": "LAP-001", "name": "Laptop", "category": "Tecnología", "quantity": 20, "min_stock": 5, "unit_price": 15000}, headers=headers)
        client.post("/api/inventory", json={"sku": "MOU-001", "name": "Mouse", "category": "Tecnología", "quantity": 2, "min_stock": 5, "unit_price": 250}, headers=headers)
        client.post("/api/inventory", json={"sku": "MUG-001", "name": "Taza", "category": "Hogar", "quantity": 0, "min_stock": 3, "unit_price": 100}, headers=headers)
        search = client.get("/api/inventory", params={"search": "lap"}, headers=headers)
        low = client.get("/api/inventory", params={"category": "Tecnología", "stock": "low"}, headers=headers)
        out = client.get("/api/inventory", params={"stock": "out"}, headers=headers)
    assert [item["sku"] for item in search.json()] == ["LAP-001"]
    assert [item["sku"] for item in low.json()] == ["MOU-001"]
    assert [item["sku"] for item in out.json()] == ["MUG-001"]


def test_inventory_update_delete_and_missing_item():
    with TestClient(app) as client:
        headers = inventory_headers(client)
        created = client.post("/api/inventory", json={"sku": "BOOK-01", "name": "Libro de pruebas", "category": "Libros", "quantity": 10, "min_stock": 2, "unit_price": 350}, headers=headers)
        item_id = created.json()["id"]
        changed = client.put(f"/api/inventory/{item_id}", json={"sku": "BOOK-01", "name": "Libro actualizado", "category": "Libros", "quantity": 6, "min_stock": 4, "unit_price": 400}, headers=headers)
        removed = client.delete(f"/api/inventory/{item_id}", headers=headers)
        missing = client.get(f"/api/inventory/{item_id}", headers=headers)
    assert created.status_code == 201
    assert changed.status_code == 200
    assert changed.json()["name"] == "Libro actualizado"
    assert changed.json()["quantity"] == 6
    assert removed.status_code == 204
    assert missing.status_code == 404


def test_inventory_rejects_duplicate_sku_and_invalid_values():
    with TestClient(app) as client:
        headers = inventory_headers(client)
        base = {"sku": "DUP-01", "name": "Producto uno", "category": "Prueba", "quantity": 1, "min_stock": 1, "unit_price": 2}
        first = client.post("/api/inventory", json=base, headers=headers)
        duplicate = client.post("/api/inventory", json={**base, "sku": "dup-01"}, headers=headers)
        invalid = client.post("/api/inventory", json={**base, "sku": "bad sku", "quantity": -1}, headers=headers)
    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert invalid.status_code == 422


def test_inventory_queries_create_database_spans(monkeypatch):
    tracer = FakeTracer()
    monkeypatch.setattr(backend_app, "request_tracer", tracer)
    with TestClient(app) as client:
        response = client.get("/api/inventory/categories", headers=inventory_headers(client))
    assert response.status_code == 200
    assert tracer.span.attributes["db.system"] == "sqlite"
    assert tracer.span.attributes["db.operation.name"] == "SELECT inventory_categories"


class FakeSpan:
    def __init__(self):
        self.attributes = {}
        self.exceptions = []
        self.status = None

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def record_exception(self, error):
        self.exceptions.append(error)

    def set_status(self, status):
        self.status = status


class FakeSpanContext:
    def __init__(self, span):
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, *_):
        return False


class FakeTracer:
    def __init__(self):
        self.span = FakeSpan()

    def start_as_current_span(self, _name):
        return FakeSpanContext(self.span)


def test_request_span_contains_normalized_route_and_status(monkeypatch):
    tracer = FakeTracer()
    monkeypatch.setattr(backend_app, "request_tracer", tracer)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert tracer.span.attributes["http.request.method"] == "GET"
    assert tracer.span.attributes["http.route"] == "/health"
    assert tracer.span.attributes["http.response.status_code"] == 200


def test_unhandled_exception_is_logged_and_marked_in_span(monkeypatch, caplog):
    tracer = FakeTracer()
    monkeypatch.setattr(backend_app, "request_tracer", tracer)

    async def fail_request():
        raise RuntimeError("simulated endpoint failure")

    route = APIRoute("/_test/exception", fail_request, methods=["GET"])
    app.router.routes.insert(len(app.router.routes) - 1, route)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/exception")
    finally:
        app.router.routes.remove(route)

    assert response.status_code == 500
    assert tracer.span.attributes["http.response.status_code"] == 500
    assert len(tracer.span.exceptions) == 1
    assert any('"event": "http_exception"' in record.message for record in caplog.records)


class FakeMeasurement:
    def __init__(self):
        self.records = []

    def add(self, value, attributes):
        self.records.append((value, attributes))

    def record(self, value, attributes):
        self.records.append((value, attributes))


def test_http_error_metrics_include_route_and_status(monkeypatch):
    requests = FakeMeasurement()
    errors = FakeMeasurement()
    latency = FakeMeasurement()
    monkeypatch.setattr(backend_app, "request_count", requests)
    monkeypatch.setattr(backend_app, "request_error_count", errors)
    monkeypatch.setattr(backend_app, "request_duration", latency)
    with TestClient(app) as client:
        response = client.patch("/api/tasks/999")
    assert response.status_code == 404
    assert len(requests.records) == len(errors.records) == len(latency.records) == 1
    assert errors.records[0][1]["http.route"] == "/api/tasks/{task_id}"
    assert errors.records[0][1]["http.response.status_code"] == 404
