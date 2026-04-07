# HTQA-SAS Event Microservice

Microservicio en FastAPI para recibir eventos operativos, validarlos, clasificarlos por severidad y persistirlos para su procesamiento.
La API expone un endpoint de salud y un endpoint de ingesta de eventos con controles de autenticación, rate limiting e idempotencia.

## Alcance del producto

Implementación acotada al MVP del caso de negocio HTQA (ingesta de eventos, idempotencia, clasificación de severidad, controles de seguridad y despliegue documentado en este repositorio). Las extensiones no descritas aquí quedan fuera de alcance.

## Objetivo funcional

- Recibir eventos vía `POST /events`.

- Validar payload y encabezado `X-API-Key`.
- Evitar duplicados recientes mediante ventana de idempotencia (TTL configurable).
- Aplicar límites por API key (ventana y cupo configurables).
- Clasificar severidad y programar procesamiento asíncrono para eventos críticos.

## Demo

![implementation](https://github.com/user-attachments/assets/f04ab853-c1ba-4a3d-91f0-f6fdb4f30a5b)

## Stack principal

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy (async) + AsyncPG / SQLite
- Redis (cache, idempotencia, rate limit)
- Pydantic v2 + pydantic-settings
- Pytest + pytest-asyncio + pytest-cov + httpx
- Black + Flake8 (desarrollo; configuración en `black.toml` y `.flake8`)
- Gestor de entorno/dependencias local: `uv`

## Arquitectura y estructura clave

El proyecto sigue una separación por capas (`domain`, `application`, `infrastructure`, `presentation`):

```text
HTQA-SAS/
├── src/
│   ├── domain/                  # Entidades, value objects, puertos
│   ├── application/             # DTOs y servicios de negocio
│   ├── infrastructure/          # DB, repositorios, notificaciones
│   ├── presentation/            # Rutas, dependencias, middlewares
│   └── main.py                  # App FastAPI y ciclo de vida
├── tests/                       # Pruebas unitarias e integración
├── deploy/                      # Guía de producción, plantilla .env, script de build
├── Dockerfile                   # Imagen dev (Compose)
├── Dockerfile.prod              # Imagen producción (multi-stage)
├── docker-compose.yml           # Dev local (variables desde .env)
├── .env.example                 # Variables de entorno de referencia
├── black.toml / .flake8         # Estilo de código (Black / Flake8)
└── pyproject.toml               # Dependencias y configuración de tests
```

Diagramas de flujo y secuencia del sistema: [FLOW_DIAGRAM.md](FLOW_DIAGRAM.md).

## Requisitos previos

- Python `>=3.11`
- `uv` instalado
- Redis disponible
- Base de datos:
  - PostgreSQL (recomendado para entorno completo), o
  - SQLite (desarrollo local)

## Configuración

1. Copia variables de entorno:

```bash
cp .env.example .env
```

2. Ajusta los valores necesarios en `.env` (no subir secretos al repositorio):

- `API_KEY`: clave esperada en el header `X-API-Key`
- `DATABASE_URL`: conexión async de SQLAlchemy
- `REDIS_URL`: conexión a Redis
- Con **Docker Compose**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` (deben coincidir con credenciales en `DATABASE_URL`) y, si hace falta, `COMPOSE_APP_PORT`, `COMPOSE_POSTGRES_PORT`, `COMPOSE_REDIS_PORT` para los puertos publicados en el host
- `RATE_LIMIT_REQUESTS`: máximo de requests por ventana
- `RATE_LIMIT_WINDOW_SECONDS`: tamaño de la ventana de rate limit
- `IDEMPOTENCY_TTL_SECONDS`: duración de la ventana de idempotencia
- `NOTIFICATION_RECIPIENT_EMAIL`: destinatario de alertas para eventos críticos (implementación mock registra en log)
- `APP_HOST`, `APP_PORT`, `LOG_LEVEL`: parámetros de ejecución/log

## Ejecución local sin Docker Compose

Sí, el proyecto puede ejecutarse sin `docker compose` usando `uv` y servicios locales.

1. Crear entorno e instalar dependencias:

```bash
uv sync --dev
```

2. Crear variables de entorno locales:

```bash
cp .env.example .env
```

3. Para ejecución local simple, usa SQLite y Redis local en `.env`:

```env
DATABASE_URL=sqlite+aiosqlite:///./htqa_events.db
REDIS_URL=redis://localhost:6379/0
APP_HOST=0.0.0.0
APP_PORT=8000
```

4. Iniciar Redis local (ejemplo con servicio del sistema o instancia equivalente).

5. Levantar la API:

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Documentación interactiva disponible en:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

6. (Opcional) Ejecutar pruebas:

```bash
uv run pytest -q
```

## Ejecución con Docker Compose

Las variables sensibles y de configuración salen del fichero **`.env`** (no versionado). Antes del primer arranque:

```bash
cp .env.example .env
```

Ajusta `API_KEY`, `POSTGRES_PASSWORD` y `DATABASE_URL` si cambias usuario o contraseña de Postgres (deben ser coherentes entre sí). Inicia el entorno de desarrollo (API y dependencias en `docker-compose.yml`) con:

```bash
docker compose up --build
```

La API queda en el puerto definido por `COMPOSE_APP_PORT` en `.env` (por defecto `8000`), por ejemplo `http://localhost:8000` (incluye `/docs` y `/redoc`).

Para detener los contenedores:

```bash
docker compose down
```

Si solo quieres detener temporalmente sin eliminar recursos de Compose:

```bash
docker compose stop
```

Nota: la imagen del contenedor instala dependencias con `pip install -e .` desde `pyproject.toml`.

## Despliegue en producción (sin Docker Compose)

En producción no se recomienda operar la pila completa con `docker compose` en el servidor. El flujo previsto es:

1. **PostgreSQL y Redis** aprovisionados aparte (servicios gestionados o instancias dedicadas).
2. **Solo la API** como imagen Docker construida con `Dockerfile.prod` (multi-stage, sin tests, usuario no root, healthcheck, Gunicorn + `uvicorn.workers.UvicornWorker`).
3. Ejecución con `docker run` o con un orquestador (Kubernetes, ECS, Cloud Run, etc.).

El runtime de producción usa `gunicorn --config gunicorn.conf.py src.main:app`, con `WEB_CONCURRENCY=2` por defecto y soporte de `X-Forwarded-*` mediante `FORWARDED_ALLOW_IPS`.

Nginx es opcional y debe ejecutarse fuera de la imagen de la API. Ejemplo de proxy inverso en [deploy/nginx/nginx.conf.example](deploy/nginx/nginx.conf.example).

Guía detallada, ejemplo de `systemd` y plantilla de variables: [deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md) y [deploy/.env.production.example](deploy/.env.production.example).

Construcción rápida de la imagen de producción:

```bash
./deploy/build.sh
# o: docker build -f Dockerfile.prod -t htqa-events:latest .
```

## Ejecución de pruebas

```bash
uv run pytest -q
```

Con cobertura:

```bash
uv run pytest --cov=src --cov-report=term-missing
```

## Lint y formato (Flake8 + Black)

Análisis estático (misma longitud de línea que Black, 100 caracteres):

```bash
uv run flake8 src/ tests/
```

Formateo con la configuración de `black.toml`:

```bash
uvx black --config black.toml .
```

Si las herramientas ya están en el entorno de desarrollo (`uv sync --dev`):

```bash
uv run black --config black.toml .
```

## Endpoints relevantes

### GET /health

Health check básico del servicio.

Respuesta esperada (200):

```json
{
  "status": "healthy",
  "service": "htqa-events"
}
```

### POST /events

Recibe un evento y responde `202 Accepted` cuando es aceptado para procesamiento.

Headers mínimos:

- `Content-Type: application/json`
- `X-API-Key: <tu_api_key>`

Payload de referencia (Meraki, evento de disponibilidad):

```bash
curl -X POST "http://localhost:8000/events" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "source": "meraki",
    "customer_id": "cli-001",
    "device_id": "sw-44",
    "event_type": "device_down",
    "occurred_at": "2026-04-05T10:12:00Z",
    "metric_value": 0,
    "metadata": {
      "site": "Bogotá",
      "ip": "10.0.2.15"
    }
  }'
```

Ejemplo adicional (otro escenario):

```bash
curl -X POST "http://localhost:8000/events" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "source": "sensor-gateway",
    "customer_id": "cust-001",
    "device_id": "dev-123",
    "event_type": "temperature.high",
    "occurred_at": "2026-04-07T12:00:00Z",
    "metric_value": 92.5,
    "metadata": {"unit": "C"}
  }'
```

Posibles estados relevantes:

- `202`: evento aceptado
- `401`: API key faltante o inválida
- `409`: evento duplicado en ventana de idempotencia
- `422`: error de validación del payload
- `429`: límite de tasa excedido
- `503`: Redis indisponible (idempotencia no puede completarse de forma segura)

## Notas operativas

- **Idempotencia:** se usa una ventana temporal (TTL, por defecto 300s) para evitar duplicados por `source + device_id + event_type`.
- **Rate limit:** ventana fija con contador en Redis (`INCR` + `EXPIRE` por clave de API key; cupo y segundos de ventana configurables; por defecto 100 requests / 60s).
- **Clasificación de severidad** (`SeverityClassifier`, reglas en orden): `metric_value` ≥ 100 → CRITICAL, ≥ 50 → HIGH; `event_type` que termina en `_down` o contiene `offline` → CRITICAL (incluye el payload de referencia con `device_down`); palabras en `event_type` (error/failure → HIGH; warning/degraded → MEDIUM); `metadata.priority` (critical/high); si no aplica ninguna regla → LOW.
- **Procesamiento crítico:** eventos clasificados como `CRITICAL` disparan una tarea en background para notificación/procesamiento adicional.
- **Arquitectura de fallos avanzada:** estrategias como DLQ/circuit-breaker/reintentos distribuidos no están implementadas aún en runtime; están fuera del alcance del MVP actual.
