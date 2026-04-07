# Despliegue en producción

`docker compose` en el servidor de producción suele considerarse una mala práctica: orquestación ad-hoc, secretos en ficheros de compose, actualizaciones poco auditables y sin integración nativa con balanceadores o políticas de red de la nube. Este proyecto separa claramente **desarrollo local** (Compose) de **producción** (solo la imagen de la API con Docker u orquestador).

## Rol de cada pieza

| Entorno | Objetivo | Mecanismo |
|---------|----------|-----------|
| Local / CI | App + Postgres + Redis con un comando | `docker compose` (`docker-compose.yml`) |
| Producción | Solo el microservicio en contenedor; bases gestionadas o aprovisionadas aparte | Imagen construida con `Dockerfile.prod` + `docker run` o ECS/Kubernetes/Cloud Run/etc. |

En producción, **PostgreSQL y Redis** deben ser servicios gestionados o VMs/contenedores **provisionados y operados fuera** de este flujo (RDS, ElastiCache, instancias con systemd, etc.). La aplicación solo necesita URLs y credenciales vía variables de entorno.

## Construir la imagen de producción

Desde el directorio `HTQA-SAS`:

```bash
docker build -f Dockerfile.prod -t htqa-events:latest .
```

La imagen resultante:

- Es multi-stage (compilación de dependencias sin arrastrar `gcc` al runtime).
- No incluye el directorio `tests/`.
- Ejecuta el proceso como usuario no root.
- Define `HEALTHCHECK` contra `GET /health` en el puerto 8000 del contenedor.
- Ejecuta la API con **Gunicorn + `uvicorn.workers.UvicornWorker`** mediante `gunicorn.conf.py`.

## Ejecutar con Docker (sin Compose)

1. Preparar un fichero de entorno con secretos reales (no versionado), p. ej. `/etc/htqa-events.env`, a partir de `deploy/.env.production.example`.
   Variables relevantes para el runtime:
   - `WEB_CONCURRENCY` (por defecto `2`): número de workers Gunicorn.
   - `FORWARDED_ALLOW_IPS` (por defecto `*` en la plantilla): IPs o CIDRs del proxy autorizados a enviar `X-Forwarded-*`. Restringirlo cuando se conozca la red del proxy.

2. Publicar el puerto y aplicar política de reinicio:

```bash
docker run -d \
  --name htqa-events \
  --restart unless-stopped \
  -p 8080:8000 \
  --env-file /ruta/segura/htqa-events.env \
  htqa-events:latest
```

El mapeo `8080:8000` expone la API en el puerto **8080** del host; el contenedor sigue escuchando en **8000**. Dentro del contenedor, el comando efectivo queda centralizado en `gunicorn.conf.py`:

```bash
gunicorn --config gunicorn.conf.py src.main:app
```

Gunicorn delega la ejecución ASGI en `uvicorn.workers.UvicornWorker`, mantiene `bind 0.0.0.0:8000`, usa `WEB_CONCURRENCY=2` por defecto y define timeouts de producción sensatos (`timeout=60`, `graceful_timeout=30`, `keepalive=5`).

3. Comprobar salud:

```bash
curl -fsS http://localhost:8080/health
```

## Proxy inverso opcional

El contenedor de la API no incluye Nginx. Para evitar el antipatrón de dos procesos no relacionados en la misma imagen, el proxy inverso debe vivir fuera de esta imagen: Nginx en el host, balanceador gestionado (ALB, Cloud Load Balancer) o un proxy sidecar separado.

El ejemplo `deploy/nginx/nginx.conf.example` muestra:

- `upstream` apuntando a `app:8000`
- `proxy_set_header Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
- soporte de WebSocket (`Upgrade` / `Connection`)
- passthrough de `GET /health`

Si se usa Nginx o un balanceador L7, mantener `proxy_headers=True` y ajustar `FORWARDED_ALLOW_IPS` a las IPs o subredes del proxy.

## systemd (VM Linux)

Para reinicios automáticos y arranque al boot sin Compose, se puede usar una unidad que envuelva `docker run` o `docker start`. Ejemplo en `deploy/systemd/htqa-events.service.example`: copiar a `/etc/systemd/system/htqa-events.service`, ajustar rutas y ejecutar `systemctl daemon-reload && systemctl enable --now htqa-events`.

## Orquestadores y PaaS

Patrones habituales (sin artefactos obligatorios en este repositorio):

- **AWS:** imagen en ECR + ECS/Fargate o EKS; RDS + ElastiCache.
- **GCP:** Artifact Registry + Cloud Run o GKE; Cloud SQL + Memorystore.
- **Azure:** ACR + Container Apps/AKS; Azure Database + Cache.

En todos los casos: variables de entorno desde el secreto del proveedor, health check contra `/health`, y escalado horizontal de réplicas stateless de esta API.

## Secretos

- No incluir `.env` de producción en el repositorio.
- Preferir secretos del orquestador o ficheros con permisos restrictivos (`chmod 600`) en la VM.

## Caso de arquitectura

Esta guía cubre despliegue en producción, escalabilidad horizontal de réplicas stateless, Postgres y Redis aprovisionados aparte, health check y proxy inverso opcional, de forma coherente con lo esperado en la evaluación de arquitectura del caso HTQA.
