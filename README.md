# Entrega continua y observabilidad en AWS EC2

Aplicación de demostración para el Proyecto Parcial 2. Mantiene un frontend JavaScript estático y una API FastAPI. El pipeline prueba backend, frontend y navegador por separado, informa el resultado a OpenObserve y sólo después construye las imágenes y despliega a EC2.

## Arquitectura

```mermaid
flowchart LR
  GH[GitHub Actions] --> B[pytest + cobertura]
  GH --> F[Jest + build frontend]
  B --> E[Playwright E2E]
  F --> E
  E --> R[Resultado a OpenObserve]
  R -->|si todo aprueba| DH[Build + push Docker Hub]
  DH -->|pull de tag SHA| EC2[EC2: frontend + API]
  EC2 -->|OTLP HTTP/gRPC| COL[OpenTelemetry Collector]
  COL --> OO[OpenObserve]
  EC2 --> HM[CPU, memoria, disco, red]
  HM --> COL
  GH -->|eventos JSON| OO
```

## Ejecutar en local

Requiere Python 3.12 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
playwright install chromium
uvicorn backend.app:app --reload
```

Para probar el backend: `pytest -q --cov=backend.app tests/test_api.py`. Para el frontend: desde `frontend`, ejecuta `npm ci`, `npm run test:ci` y `npm run build`. Playwright requiere que la aplicación esté levantada y corre con `pytest -q tests/test_e2e.py`. La API sirve la interfaz local bajo el mismo host; en producción Nginx sirve el frontend en su contenedor y reenvía las llamadas a la API.

## GitHub Actions y secretos

Configura estos secrets en **Settings → Secrets and variables → Actions**:

| Secret | Valor |
| --- | --- |
| `DOCKERHUB_USERNAME` | Usuario de Docker Hub |
| `DOCKERHUB_TOKEN` | Token de acceso Docker Hub con permiso de escritura |
| `EC2_HOST` | IP pública o DNS de la EC2 |
| `EC2_SSH_KEY` | Clave privada SSH completa de despliegue |
| `EC2_KNOWN_HOSTS` | Clave pública de host SSH conocida para validar el servidor |
| `OO_URL` | `http://localhost:5080`, reenviado por túnel SSH privado |
| `OO_USER` | Usuario OpenObserve |
| `OO_PASSWORD` | Contraseña OpenObserve |

El flujo tiene jobs separados para pytest/cobertura y Jest/build; Playwright depende de ambos. Un job de reporte se ejecuta siempre y envía el resultado agregado a OpenObserve aunque una prueba falle. El build/push de Docker y el despliegue SSH dependen del éxito de todas las pruebas y del reporte; se ejecutan sólo en `main`. Un fallo de prueba no inicia el job de despliegue. Los eventos quedan en el stream `ci_pipeline`.

## Preparar EC2

La instancia de demostración activa es Ubuntu x86_64 `t3.small` en `us-east-2`, con 2 GiB de RAM y 2 GiB de swap. OpenObserve puede funcionar con este tamaño, pero 4 GiB o más dan margen para cargas mayores. El grupo de seguridad permite TCP/80 y TCP/22; SSH usa una llave Ed25519 y debe restringirse a rangos de confianza cuando sea posible. No publiques 5080 ni 4317/4318. El workflow instala Docker Engine y Compose plugin, configura `~/parcial2/.env` con permisos privados y actualiza los servicios después de las pruebas. Conserva las credenciales y claves fuera del repositorio.

La consola de OpenObserve queda ligada a `127.0.0.1:5080`; no tiene exposición pública. En PowerShell, abre el túnel y deja esa terminal activa:

```powershell
ssh -i "$env:USERPROFILE\.ssh\parcial2-cicd-ec2" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$env:USERPROFILE\.ssh\parcial2-ec2-known-hosts-correct" -N -L 5080:127.0.0.1:5080 ubuntu@18.116.201.62
```

Después abre `http://localhost:5080`. El tablero **Parcial 2 CI CD y Observabilidad** tiene siete paneles: eventos `test`/`deploy`, solicitudes y latencia HTTP, CPU, memoria, tráfico de red y trazas de la API. El flujo validado registra eventos en `ci_pipeline`. El JSON exportado del tablero está en [`observability/dashboard.json`](observability/dashboard.json). Las reglas de alerta y su destino de notificación aún deben configurarse desde OpenObserve.

## Alcance medible

El collector reporta CPU, memoria, almacenamiento, paginación y red de Linux. EC2 no expone de forma estándar temperatura física del host en una VM; por eso no se puede afirmar una gráfica de temperatura fiable sin sensor o métrica del proveedor. La aplicación emite logs estructurados, métricas OTLP de conteo, latencia y errores por método, ruta y código HTTP, y spans HTTP explícitos. La demo no usa una base de datos, así que no tiene spans de consultas SQL. Se verificó la recepción HTTP 200 de logs, métricas y trazas en OpenObserve.

## URLs

- Repositorio: https://github.com/axelisaak10/parcial2-cicd-observabilidad
- Imagen API (Docker Hub): https://hub.docker.com/r/34axel/parcial2-api
- Imagen frontend (Docker Hub): https://hub.docker.com/r/34axel/parcial2-frontend
- Aplicación EC2: http://18.116.201.62/ (salud: http://18.116.201.62/health)
- OpenObserve: http://localhost:5080 tras iniciar el túnel SSH; credenciales fuera del repositorio.
