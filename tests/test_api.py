from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import app as backend_app

app = backend_app.app
tasks = backend_app.tasks


def setup_function():
    tasks.clear()
    backend_app.next_id = 1


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
