"""Idempotently install the inventory observability dashboard and alerts."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("OO_URL", "http://127.0.0.1:5080").rstrip("/")
ORG = os.getenv("OO_ORG", "default")
USER = os.getenv("ZO_ROOT_USER_EMAIL", "")
PASSWORD = os.getenv("ZO_ROOT_USER_PASSWORD", "")


def api(method: str, path: str, body: dict | None = None) -> dict:
    if not USER or not PASSWORD:
        raise RuntimeError("OpenObserve credentials are not configured in the deployment environment")
    auth = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"OpenObserve {method} {path} failed ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"OpenObserve {method} {path} is unreachable: {exc.reason}") from exc


def provision_dashboard(path: Path) -> None:
    dashboard = json.loads(path.read_text(encoding="utf-8"))
    dashboard_id = dashboard["dashboardId"]
    api("PUT", f"/api/{ORG}/dashboards/{dashboard_id}", dashboard)
    print(f"Dashboard actualizado: {dashboard['title']}")


def alert(name: str, stream: str, promql: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "stream_type": "metrics",
        "stream_name": stream,
        "is_real_time": False,
        "enabled": True,
        "destinations": [],
        "query_condition": {"type": "promql", "promql": promql},
        "trigger_condition": {
            "period": 5,
            "frequency": 1,
            "frequency_type": "minutes",
            "operator": ">=",
            "threshold": 1,
            "silence": 10,
        },
        "tz_offset": -360,
    }


ALERTS = [
    alert(
        "frontend_request_load_high",
        "nginx_http_requests_total",
        "sum(rate(nginx_http_requests_total[5m])) > 25",
        "El frontend NGINX recibe más de 25 solicitudes por segundo durante la ventana de evaluación.",
    ),
    alert(
        "frontend_connections_high",
        "nginx_connections_active",
        "max(nginx_connections_active) > 40",
        "Hay más de 40 conexiones activas en el frontend.",
    ),
    alert(
        "backend_requests_in_flight_high",
        "http_server_active_requests",
        "max(http_server_active_requests) > 15",
        "La API mantiene más de 15 solicitudes simultáneas en curso.",
    ),
    alert(
        "backend_http_errors_detected",
        "http_server_error_count",
        'sum(increase(http_server_error_count{http_response_status_code=~"5.."}[5m])) > 0',
        "La API registró respuestas HTTP 5xx durante los últimos cinco minutos.",
    ),
    alert(
        "ec2_cpu_load_high",
        "system_cpu_load_average_1m",
        "max(system_cpu_load_average_1m) > 1.5",
        "La carga promedio de CPU a un minuto superó 1.5 en la instancia EC2.",
    ),
    alert(
        "ec2_memory_pressure",
        "system_memory_usage",
        'max(system_memory_usage{state="used"}) > 1800000000',
        "El consumo de memoria usada superó 1.8 GB en EC2.",
    ),
]


REQUIRED_STREAMS = {
    "http_server_request_count",
    "http_server_error_count",
    "http_server_active_requests",
    "nginx_http_requests_total",
    "nginx_connections_active",
    "system_cpu_load_average_1m",
    "system_memory_usage",
    "system_network_io",
}


def wait_for_metrics(timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    missing = REQUIRED_STREAMS.copy()
    while time.monotonic() < deadline:
        result = api("GET", f"/api/{ORG}/streams")
        now_us = int(time.time() * 1_000_000)
        current = {}
        for item in result.get("list", []):
            if item.get("stream_type") != "metrics":
                continue
            stats = item.get("stats", {})
            latest = stats.get("doc_time_max", 0)
            age_us = now_us - latest if latest else None
            if stats.get("doc_num", 0) and age_us is not None and -120_000_000 <= age_us <= 120_000_000:
                current[item.get("name")] = latest
        missing = REQUIRED_STREAMS - current.keys()
        if not missing:
            print("Telemetría reciente verificada en OpenObserve: API, frontend y host EC2")
            return
        time.sleep(15)
    raise RuntimeError("Faltan métricas recientes en OpenObserve: " + ", ".join(sorted(missing)))


def provision_alerts() -> None:
    result = api("GET", f"/api/v2/{ORG}/alerts?page_size=1000&page_idx=0")
    existing = {item.get("name"): item for item in result.get("list", [])}
    for definition in ALERTS:
        current = existing.get(definition["name"])
        if current:
            alert_id = current.get("alert_id") or current.get("id")
            if not alert_id:
                raise RuntimeError(f"OpenObserve no devolvió el identificador de {definition['name']}")
            api("PUT", f"/api/v2/{ORG}/alerts/{alert_id}", definition)
            action = "actualizada"
        else:
            api("POST", f"/api/v2/{ORG}/alerts", definition)
            action = "creada"
        print(f"Alerta {action}: {definition['name']}")


def main() -> int:
    dashboard = Path(sys.argv[1] if len(sys.argv) > 1 else "observability/dashboard.json")
    try:
        wait_for_metrics()
        provision_dashboard(dashboard)
        provision_alerts()
    except (OSError, KeyError, RuntimeError, ValueError) as exc:
        print(f"Error al preparar observabilidad: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
