from __future__ import annotations

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(message)s")
logger = logging.getLogger("ci_cd_demo")
tasks: list[dict] = []
next_id = 1

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
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "ci-cd-demo-api")})
        metric_exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/metrics")
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(metric_exporter)]))
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")))
        trace.set_tracer_provider(tracer_provider)
        meter = metrics.get_meter("ci_cd_demo")
        request_count = meter.create_counter("http.server.request.count", unit="{request}")
        request_duration = meter.create_histogram("http.server.request.duration", unit="s")
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/logs")))
        logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    else:
        request_count = request_duration = None
except ImportError:
    request_count = request_duration = None


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


@app.middleware("http")
async def request_log(request: Request, call_next):
    response: Response | None = None
    import time
    started = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.perf_counter() - started
        code = response.status_code if response else 500
        attributes = {"http.request.method": request.method, "http.route": request.url.path, "http.response.status_code": code}
        if request_count:
            request_count.add(1, attributes)
            request_duration.record(elapsed, attributes)
        logger.info(
            '{"event":"http_request","method":"%s","path":"%s","status_code":%s,"duration_seconds":%.6f}',
            request.method,
            request.url.path,
            code,
            elapsed,
        )


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


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    FastAPIInstrumentor.instrument_app(app)
