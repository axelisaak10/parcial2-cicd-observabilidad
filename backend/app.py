from __future__ import annotations

import logging
import json
import os
import sqlite3
import binascii
import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("ci_cd_demo")
tasks: list[dict] = []
next_id = 1
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", Path(__file__).resolve().parent.parent / ".local" / "inventory.db"))


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity >= 0),
            min_stock INTEGER NOT NULL CHECK (min_stock >= 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            location TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    return connection


@contextmanager
def db_connection():
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def item_dict(row: sqlite3.Row) -> dict:
    return dict(row)


@contextmanager
def database_span(operation: str):
    if not request_tracer:
        yield
        return
    with request_tracer.start_as_current_span(f"sqlite.{operation}") as span:
        span.set_attribute("db.system", "sqlite")
        span.set_attribute("db.operation.name", operation)
        span.set_attribute("db.namespace", DATABASE_PATH.name)
        yield

try:
    from opentelemetry import metrics
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "ci-cd-demo-api")})
        metric_exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/metrics")
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(metric_exporter)]))
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")))
        trace.set_tracer_provider(tracer_provider)
        request_tracer = trace.get_tracer("ci_cd_demo.http")
        meter = metrics.get_meter("ci_cd_demo")
        request_count = meter.create_counter("http.server.request.count", unit="{request}")
        request_error_count = meter.create_counter("http.server.error.count", unit="{error}")
        request_duration = meter.create_histogram("http.server.request.duration", unit="s")
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/logs")))
        logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    else:
        request_count = request_duration = None
        request_error_count = None
        request_tracer = None
except ImportError:
    request_count = request_duration = None
    request_error_count = None
    request_tracer = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info('{"event":"application_started","service":"ci-cd-demo-api"}')
    yield
    logger.info('{"event":"application_stopped","service":"ci-cd-demo-api"}')


app = FastAPI(title="CI/CD Observability Demo API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class TaskInput(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]


class InventoryInput(BaseModel):
    sku: Annotated[str, Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9._-]+$")]
    name: Annotated[str, Field(min_length=2, max_length=100)]
    category: Annotated[str, Field(min_length=2, max_length=40)] = "General"
    quantity: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    min_stock: Annotated[int, Field(ge=0, le=1_000_000)] = 5
    unit_price: Annotated[float, Field(ge=0, le=10_000_000)] = 0
    location: Annotated[str, Field(min_length=2, max_length=80)] = "Almacén principal"
    description: Annotated[str, Field(max_length=300)] = ""

    def clean_values(self) -> dict:
        values = self.model_dump()
        for field in ("sku", "name", "category", "location", "description"):
            values[field] = values[field].strip()
        if len(values["sku"]) < 2 or len(values["name"]) < 2:
            raise HTTPException(status_code=422, detail="SKU y nombre deben tener al menos 2 caracteres")
        return values


class LoginInput(BaseModel):
    username: Annotated[str, Field(min_length=1, max_length=80)]
    password: Annotated[str, Field(min_length=1, max_length=200)]


def create_access_token(username: str) -> str:
    secret = os.getenv("INVENTORY_TOKEN_SECRET", "")
    payload = json.dumps({"sub": username, "exp": int(time.time()) + 12 * 60 * 60}, separators=(",", ":")).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(secret.encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def verify_access_token(token: str) -> str | None:
    secret = os.getenv("INVENTORY_TOKEN_SECRET", "")
    admin_user = os.getenv("INVENTORY_ADMIN_USER", "")
    if not secret or not admin_user:
        return None
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        expected = base64.urlsafe_b64encode(expected_signature).rstrip(b"=").decode()
        if not hmac.compare_digest(supplied_signature, expected):
            return None
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if payload.get("sub") != admin_user or int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return admin_user
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        return None


async def require_inventory_admin(authorization: Annotated[str | None, Header()] = None) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        user = verify_access_token(authorization[7:].strip())
        if user:
            return user
    raise HTTPException(status_code=401, detail="La sesión no es válida o expiró. Inicia sesión nuevamente.", headers={"WWW-Authenticate": "Bearer"})


@app.middleware("http")
async def request_log(request: Request, call_next):
    response: Response | None = None
    import time
    started = time.perf_counter()
    span_context = request_tracer.start_as_current_span(f"{request.method} {request.url.path}") if request_tracer else None
    try:
        if span_context:
            with span_context as span:
                span.set_attribute("http.request.method", request.method)
                try:
                    response = await call_next(request)
                except Exception as exc:
                    span.set_attribute("http.response.status_code", 500)
                    from opentelemetry.trace import Status, StatusCode
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    raise
                route = request.scope.get("route")
                endpoint = getattr(route, "path", request.url.path)
                span.set_attribute("http.route", endpoint)
                span.set_attribute("http.response.status_code", response.status_code)
                if response.status_code >= 500:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR))
                return response
        response = await call_next(request)
        return response
    except Exception:
        logger.exception(json.dumps({
            "event": "http_exception",
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        }))
        raise
    finally:
        elapsed = time.perf_counter() - started
        code = response.status_code if response else 500
        route = request.scope.get("route")
        endpoint = getattr(route, "path", request.url.path)
        attributes = {"http.request.method": request.method, "http.route": endpoint, "http.response.status_code": code}
        if request_count:
            request_count.add(1, attributes)
            request_duration.record(elapsed, attributes)
            if code >= 400:
                request_error_count.add(1, attributes)
        logger.info(json.dumps({
            "event": "http_request",
            "method": request.method,
            "path": endpoint,
            "status_code": code,
            "duration_seconds": round(elapsed, 6),
            "timestamp_unix_ns": time.time_ns(),
        }))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ci-cd-demo-api"}


@app.get("/api/tasks")
async def list_tasks():
    return tasks


@app.post("/api/tasks", status_code=201)
async def create_task(payload: TaskInput):
    global next_id
    task = {"id": next_id, "title": payload.title.strip(), "done": False}
    next_id += 1
    tasks.append(task)
    logger.info('{"event":"task_created","task_id":%s}', task["id"])
    return task


@app.patch("/api/tasks/{task_id}")
async def complete_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            return task
    raise HTTPException(status_code=404, detail="Tarea no encontrada")


@app.post("/api/auth/login")
async def login(payload: LoginInput):
    admin_user = os.getenv("INVENTORY_ADMIN_USER", "")
    admin_password = os.getenv("INVENTORY_ADMIN_PASSWORD", "")
    token_secret = os.getenv("INVENTORY_TOKEN_SECRET", "")
    if not admin_user or not admin_password or not token_secret:
        raise HTTPException(status_code=503, detail="El acceso de administrador aún no está configurado")
    if not hmac.compare_digest(payload.username.encode(), admin_user.encode()) or not hmac.compare_digest(payload.password.encode(), admin_password.encode()):
        logger.warning('{"event":"inventory_login_failed"}')
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    logger.info('{"event":"inventory_login_succeeded"}')
    return {"access_token": create_access_token(admin_user), "token_type": "bearer", "expires_in": 43200, "username": admin_user}


@app.get("/api/inventory/summary")
async def inventory_summary(_user: Annotated[str, Depends(require_inventory_admin)]):
    with database_span("SELECT inventory_summary"):
        with db_connection() as connection:
            row = connection.execute("""
                SELECT COUNT(*) AS products,
                       COALESCE(SUM(quantity), 0) AS units,
                       COALESCE(SUM(CASE WHEN quantity = 0 THEN 1 ELSE 0 END), 0) AS out_of_stock,
                       COALESCE(SUM(CASE WHEN quantity > 0 AND quantity <= min_stock THEN 1 ELSE 0 END), 0) AS low_stock,
                       COALESCE(SUM(quantity * unit_price), 0) AS inventory_value
                FROM inventory_items
            """).fetchone()
    return dict(row)


@app.get("/api/inventory")
async def list_inventory(
    _user: Annotated[str, Depends(require_inventory_admin)],
    search: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=40)] = None,
    stock: Annotated[str | None, Query(pattern=r"^(all|in_stock|low|out)$")] = "all",
):
    clauses: list[str] = []
    params: list[str | int] = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        clauses.append("(name LIKE ? OR sku LIKE ? OR category LIKE ? OR location LIKE ?)")
        params.extend([term, term, term, term])
    if category and category != "Todas":
        clauses.append("category = ?")
        params.append(category)
    if stock == "in_stock":
        clauses.append("quantity > min_stock")
    elif stock == "low":
        clauses.append("quantity > 0 AND quantity <= min_stock")
    elif stock == "out":
        clauses.append("quantity = 0")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with database_span("SELECT inventory_items"):
        with db_connection() as connection:
            rows = connection.execute(f"SELECT * FROM inventory_items {where} ORDER BY name COLLATE NOCASE", params).fetchall()
    return [item_dict(row) for row in rows]


@app.get("/api/inventory/categories")
async def list_inventory_categories(_user: Annotated[str, Depends(require_inventory_admin)]):
    with database_span("SELECT inventory_categories"):
        with db_connection() as connection:
            rows = connection.execute("SELECT DISTINCT category FROM inventory_items ORDER BY category COLLATE NOCASE").fetchall()
    return [row["category"] for row in rows]


@app.get("/api/inventory/{item_id}")
async def get_inventory_item(item_id: int, _user: Annotated[str, Depends(require_inventory_admin)]):
    with database_span("SELECT inventory_item"):
        with db_connection() as connection:
            row = connection.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return item_dict(row)


@app.post("/api/inventory", status_code=201)
async def create_inventory_item(payload: InventoryInput, _user: Annotated[str, Depends(require_inventory_admin)]):
    values = payload.clean_values()
    now = datetime.now(timezone.utc).isoformat()
    with database_span("INSERT inventory_item"):
        with db_connection() as connection:
            try:
                cursor = connection.execute("""
                    INSERT INTO inventory_items (sku, name, category, quantity, min_stock, unit_price, location, description, created_at, updated_at)
                    VALUES (:sku, :name, :category, :quantity, :min_stock, :unit_price, :location, :description, :now, :now)
                """, {**values, "now": now})
                row = connection.execute("SELECT * FROM inventory_items WHERE id = ?", (cursor.lastrowid,)).fetchone()
            except sqlite3.IntegrityError as exc:
                if "sku" in str(exc).lower():
                    raise HTTPException(status_code=409, detail="Ya existe un producto con ese SKU") from exc
                raise HTTPException(status_code=422, detail="Los datos del producto no son válidos") from exc
    logger.info(json.dumps({"event": "inventory_item_created", "item_id": row["id"], "sku": row["sku"]}))
    return item_dict(row)


@app.put("/api/inventory/{item_id}")
async def update_inventory_item(item_id: int, payload: InventoryInput, _user: Annotated[str, Depends(require_inventory_admin)]):
    values = payload.clean_values()
    now = datetime.now(timezone.utc).isoformat()
    with database_span("UPDATE inventory_item"):
        with db_connection() as connection:
            if connection.execute("SELECT 1 FROM inventory_items WHERE id = ?", (item_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Producto no encontrado")
            try:
                connection.execute("""
                    UPDATE inventory_items
                    SET sku=:sku, name=:name, category=:category, quantity=:quantity, min_stock=:min_stock,
                        unit_price=:unit_price, location=:location, description=:description, updated_at=:now
                    WHERE id=:id
                """, {**values, "now": now, "id": item_id})
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Ya existe un producto con ese SKU") from exc
            row = connection.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
    logger.info(json.dumps({"event": "inventory_item_updated", "item_id": item_id, "sku": row["sku"]}))
    return item_dict(row)


@app.delete("/api/inventory/{item_id}", status_code=204)
async def delete_inventory_item(item_id: int, _user: Annotated[str, Depends(require_inventory_admin)]):
    with database_span("DELETE inventory_item"):
        with db_connection() as connection:
            cursor = connection.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    logger.info(json.dumps({"event": "inventory_item_deleted", "item_id": item_id}))
    return Response(status_code=204)


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
