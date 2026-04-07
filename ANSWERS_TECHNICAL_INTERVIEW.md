# RESPUESTA A PRUEBA TÉCNICA – DESARROLLADOR SENIOR PYTHON

**HTQA S.A.S. | Evaluación Técnica Senior**

---

## 1. Contexto del Caso

El sistema actual de HTQA S.A.S. sufre de **duplicidad de eventos**, **baja trazabilidad** y **dificultades de escalabilidad**.

**Solución implementada (estado actual):** Microservicio en Python + FastAPI con arquitectura por capas que cubre el alcance MVP:
- **Duplicidad** → Idempotencia con Redis (SETNX atómico, ventana 5 min)
- **Trazabilidad** → Audit middleware + logging estructurado
- **Escalabilidad** → Procesamiento asíncrono local (BackgroundTasks) y despliegue contenedorizado (Compose en desarrollo; producción con imagen dedicada y orquestación externa, ver `deploy/DEPLOYMENT.md`)

---

## 2. Objetivo

Microservicio backend orientado a eventos con arquitectura limpia, seguridad y escalabilidad.

**Stack:** FastAPI (async) + PostgreSQL (SQLAlchemy 2.0) + Redis + Pydantic v2 + Docker (Compose solo para desarrollo local; producción documentada en `deploy/DEPLOYMENT.md`).

**Arquitectura:** Clean/Hexagonal — domain → application → infrastructure → presentation.

---

## 3. Payload de Referencia

Validado por `EventCreateDTO` (Pydantic) con campos obligatorios: `source`, `customer_id`, `device_id`, `event_type`, `occurred_at`, `metric_value`. El campo `metadata` es opcional (si se omite, se usa `{}`). Cualquier clave adicional no definida en el modelo provoca 422 por `extra="forbid"`.

---

## 4. Desarrollo del Servicio

### 4.1 Endpoint `POST /events`

**Validación:** Pydantic DTO con `min_length`, `max_length`, tipos estrictos. Campo `metadata` opcional con default `{}`.

**Manejo de errores:** `HTTPException` con códigos de estado documentados: 202, 401, 409, 422, 429, 503 (p. ej. Redis indisponible para idempotencia).

**Logging:** `logging.basicConfig` en `main.py` + AuditMiddleware captura cada request.

**Respuesta estructurada:** `EventResponseDTO` con id (UUID), severity, status y timestamps.

**Dónde está la lógica de negocio:** En `application/services/` (`EventService`), NO en los routers. El router solo: valida DTO → delega al service → devuelve respuesta. El service orquesta: rate limit → idempotencia → clasificación → persistencia → notificación.

### 4.2 Idempotencia (CRÍTICO)

**Estrategia:** Redis con clave `idempotency:{source}:{device_id}:{event_type}`, TTL de 300 s (5 min). Incluye `source` para alinear la deduplicación con el origen del evento (el mismo dispositivo y tipo desde otro origen no se considera duplicado). Operación atómica `SETNX` (`nx=True, ex=ttl`) en un solo comando Redis — no hay check-then-create separado.

**Manejo de concurrencia:** Redis es single-threaded, `SETNX` es atómico por naturaleza. Dos requests concurrentes con el mismo `source` + `device_id` + `event_type`: solo uno gana; el otro recibe 409 Conflict.

**Flujo:** `check_and_store` → si la clave no existe, la crea con valor "pending" → persiste evento → `mark_completed` actualiza con el `event_id` real.

### 4.3 Clasificación de Severidad

**Implementación:** `SeverityClassifier` independiente, inyectado como dependencia. Reglas (orden): `metric_value` ≥ 100 → CRITICAL, ≥ 50 → HIGH; `event_type` que termina en `_down` o contiene `offline` → CRITICAL (p. ej. `device_down` del payload de referencia); "error"/"failure" en `event_type` → HIGH; "warning"/"degraded" → MEDIUM; `metadata.priority` → override; default → LOW.

**Extensibilidad:** Implementada con contrato `SeverityRule` y composición de reglas inyectables en `SeverityClassifier`. Para agregar reglas, se crea una nueva clase de regla y se inyecta en el classifier, sin modificar su lógica interna (OCP).

### 4.4 Procesamiento Asíncrono

**Implementación:** FastAPI `BackgroundTasks`. El endpoint devuelve 202 Accepted inmediatamente. Si el evento es CRITICAL, se agenda `background_tasks.add_task(self._process_critical_event, event_id)`. El cliente no espera la notificación.

**Por qué BackgroundTasks:** Simple, no requiere infraestructura adicional (Celery/RabbitMQ). Para producción a escala: migrar a Celery con retry policies y dead letter queue.

**Resiliencia en notificación:** si el envío falla en la tarea de background, el evento pasa a `FAILED` y se registra error en logs; el request principal ya respondió 202.

---

## 5. Diseño y Principios SOLID

### 5.1 SRP — Responsabilidad Única

Cada clase tiene un solo motivo para cambiar:

| Clase | Responsabilidad |
|-------|----------------|
| `EventService` | Orquestar flujo de creación |
| `SeverityClassifier` | Clasificar severidad |
| `IdempotencyService` | Verificar duplicados |
| `RateLimiterService` | Controlar tasa de requests |
| `NotificationService` | Enviar alertas |
| `SQLAlchemyEventRepository` | Persistir en PostgreSQL |
| `RedisCacheRepository` | Operaciones de caché Redis para idempotencia y rate limiting |
| `AuditMiddleware` | Capturar metadata de requests |

Contra-ejemplo del código original: una sola función hacía idempotencia + clasificación + persistencia + notificación (5 responsabilidades).

### 5.2 OCP — Abierto/Cerrado

**Ports abstractos** permiten extender sin modificar: `NotificationServicePort` se puede implementar con Email, Slack, SNS o PagerDuty sin tocar `NotificationService`. `CacheRepository` se puede cambiar de Redis a otro backend sin tocar los services. Las reglas de severidad se extienden con `SeverityRule` sin modificar `SeverityClassifier`.

### 5.3 DIP — Inversión de Dependencias

`EventService` depende del puerto de repositorio de eventos y de servicios de aplicación inyectados por DI. En infraestructura se usan implementaciones concretas (`SQLAlchemyEventRepository`, `RedisCacheRepository`, `MockEmailNotifier`) y se inyectan mediante FastAPI `Depends()`. El desacople principal queda logrado en repositorio/cache/notificador; puede reforzarse aún más para todos los servicios de aplicación con puertos dedicados.

---

## 6. Seguridad

| Requisito | Implementación |
|-----------|---------------|
| **Autenticación** | API Key vía header `X-API-Key`, validada en dependencia FastAPI |
| **Validación de entrada** | Pydantic DTO con tipos estrictos, min/max length |
| **Rate limiting** | Ventana fija con contador en Redis (`INCR` + `EXPIRE` por `rate_limit:{api_key}`); cupo y ventana configurables (`RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`) |
| **Manejo de secretos** | Variables de entorno (.env), `.env.example` sin credenciales, `.gitignore` excluye `.env` |
| **Destinatario de alertas críticas** | `NOTIFICATION_RECIPIENT_EMAIL` vía `Settings` / Pydantic; inyectado en `NotificationService` (sin email hardcodeado en el servicio) |
| **Logging seguro** | Headers sensibles redactados (Authorization, X-API-Key), API key truncada en audit |
| **Auditoría** | `AuditMiddleware` captura: timestamp, api_key (truncada), method, path, status_code, ip_address |

---

## 7. Revisión de Código

Código bajo revisión (proporcionado en la prueba):

```python
def create_event(payload, db, notifier):
    event = db.query(Event).filter_by(
        source=payload["source"], device_id=payload["device_id"]).first()
    if event: return event
    if payload.get("event_type") == "device_down": severity = "critical"
    else: severity = "low"
    e = Event(**payload, severity=severity, status="processed")
    db.add(e); db.commit()
    notifier.send_email("ops@company.com", f"nuevo evento {e.id}")
    return e
```

**12 problemas identificados:**

| # | Problema | Categoría | Severidad |
|---|----------|-----------|-----------|
| 1 | **Idempotencia rota** — filtra solo source+device_id, ignora event_type y tiempo | Bug | 🔴 |
| 2 | **Race condition** — check-then-create no es atómico bajo concurrencia | Concurrencia | 🔴 |
| 3 | **KeyError potencial** — `payload["source"]` falla si falta la clave | Robustez | 🔴 |
| 4 | **`payload` sin sanitizar** — campos inesperados pueden sobrescribir severity/status | Seguridad | 🔴 |
| 5 | **Sin manejo de errores** — no hay try/except ni rollback si commit falla | Robustez | 🟡 |
| 6 | **Notificación síncrona bloqueante** — `send_email()` bloquea el request | Performance | 🟡 |
| 7 | **Email hardcodeado** — `"ops@company.com"` no es configurable | Maintainability | 🟡 |
| 8 | **Status "processed" prematuro** — se marca como procesado antes de notificar | Lógica | 🟡 |
| 9 | **Viola SRP** — 5 responsabilidades en una función | Diseño | 🟡 |
| 10 | **Viola DIP** — depende de concretos (db session, email), no de interfaces | Diseño | 🟡 |
| 11 | **Viola OCP** — severidad hardcodeada con if/else, no extensible | Diseño | 🟠 |
| 12 | **Sin logging/auditoría** — cero trazabilidad | Observabilidad | 🟠 |

**Cómo se resuelve en la aplicación:** Pydantic DTO (P3, P4), Redis `SETNX` atómico (P1, P2), `BackgroundTasks` (P6), settings configurables (P7), status PENDING→PROCESSED (P8), servicios separados (P9), desacople por puertos/adaptadores (P10), reglas de severidad extensibles (P11), `AuditMiddleware` (P12).
**Nota de alcance:** el punto 7 de la prueba es de análisis del snippet (mínimo 8 problemas), no exige feature adicional en runtime.

---

## 8. Arquitectura

### Despliegue

**Desarrollo:** `docker compose up` levanta app + PostgreSQL + Redis con health checks (`docker-compose.yml`); variables desde `.env` (plantilla `.env.example`), sin secretos fijados en el YAML.

**Producción:** Imagen multi-stage `Dockerfile.prod` (sin tests, usuario no root, `HEALTHCHECK` sobre `/health`) ejecutada con **Gunicorn + `uvicorn.workers.UvicornWorker`** mediante `gunicorn.conf.py`. `WEB_CONCURRENCY` controla el número de workers (default 2) y `FORWARDED_ALLOW_IPS` permite confiar explícitamente en `X-Forwarded-*` cuando la API está detrás de Nginx/ALB. Ejecución documentada con `docker run` + variables de entorno apuntando a Postgres/Redis gestionados; ejemplo de unidad `systemd` en `deploy/systemd/` y ejemplo de proxy en `deploy/nginx/nginx.conf.example`. No se usa Compose en el servidor de producción ni Nginx embebido en la misma imagen. Manifiestos Kubernetes/ECS/Cloud Run no se incluyen como artefactos (patrones descritos en `deploy/DEPLOYMENT.md`).

### Escalabilidad

| Componente | Escala horizontal | Estrategia |
|-----------|------------------|------------|
| **App** | ✅ Stateless, múltiples réplicas | K8s HPA por CPU/latencia |
| **Redis** | ✅ Sentinel (HA) o Cluster (sharding) | Single node suficiente para MVP |
| **PostgreSQL** | ✅ Read replicas + PgBouncer | Primary para writes, replicas para reads |

### Manejo de Fallos

| Escenario | Estado en implementación actual |
|-----------|-------------------------------|
| Redis caído / inestable | Rate limit en modo **fail-open** (permite tráfico y registra advertencia); idempotencia devuelve **503** al fallar caché; cliente Redis con cierre en shutdown |
| PostgreSQL caído / conexión perdida | `pool_pre_ping` + `pool_recycle` en SQLAlchemy; errores de persistencia se propagan para manejo por capa superior |
| Notificación falla | Sin reintentos en servicio; la tarea background marca el evento `FAILED` y registra error |
| Crash del proceso | Recuperación delegada al entorno de despliegue (sin cola persistente de trabajo en el repo) |
| Graceful shutdown | Cierre ordenado de conexión Redis (`aclose`) y dispose del motor SQLAlchemy en el lifespan de FastAPI |

---

## 9. SQL

### Consulta: Eventos críticos últimas 24h

```sql
SELECT id, source, customer_id, device_id, event_type,
       occurred_at, metric_value, metadata, severity, status, created_at
FROM events
WHERE severity = 'critical'
  AND occurred_at >= NOW() - INTERVAL '24 hours'
ORDER BY occurred_at DESC;
```

Implementada en `SQLAlchemyEventRepository.get_critical_events(hours=24)`.

### Índices

```sql
-- Compuesto para query de 24h (severity + tiempo en un solo seek)
CREATE INDEX idx_events_severity_occurred_at ON events (severity, occurred_at);

-- Lookup por clave natural (origen + dispositivo + tipo)
CREATE INDEX idx_events_source_device_event ON events (source, device_id, event_type);

-- Consultas multi-tenant por cliente
CREATE INDEX idx_events_customer_created ON events (customer_id, created_at);

-- Parcial (declarado en ORM): alinea filtro severity = critical + ORDER BY occurred_at DESC
CREATE INDEX idx_events_critical_recent ON events (occurred_at DESC)
WHERE severity = 'critical';
```

**Implementación:** `EventModel` en `src/infrastructure/database/models.py` define el índice parcial con `Index(..., postgresql_ops={'occurred_at': 'DESC'}, postgresql_where=...)`.

### Partición

Partición por **RANGE** sobre `occurred_at` (límites mensuales en UTC), PK compuesta `(id, occurred_at)` en el modelo, y DDL en `after_create` que crea particiones del **mes actual**, **mes siguiente** y **DEFAULT** (`src/infrastructure/database/partition_ddl.py`, importado desde `session.py` antes de `create_all`):

```sql
CREATE TABLE events (...) PARTITION BY RANGE (occurred_at);
-- Hijos (nombres generados en runtime, p. ej. events_p_2026_04, events_default)
CREATE TABLE events_p_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01T00:00:00+00:00') TO ('2026-05-01T00:00:00+00:00');
```

---

*HTQA S.A.S. — Prueba Técnica Desarrollador Senior Python*
