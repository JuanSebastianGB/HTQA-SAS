"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infrastructure.database.session import init_db_session
from src.presentation.dependencies import get_settings
from src.presentation.dependencies.auth import get_redis, init_redis
from src.presentation.middleware.audit import AuditMiddleware
from src.presentation.routes.events import router as events_router
from src.presentation.routes.health import router as health_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting HTQA Event Microservice...")

    settings = get_settings()

    # Initialize database - use environment variable or fallback to docker service name
    db_session = init_db_session(settings.database_url)
    await db_session.create_tables()
    logger.info("Database initialized")

    # Initialize Redis
    init_redis(settings.redis_url)
    logger.info("Redis initialized")

    yield

    # Shutdown
    logger.info("Shutting down HTQA Event Microservice...")
    try:
        redis_client = get_redis()
        await redis_client.aclose()
    except Exception as exc:
        logger.warning("Redis shutdown: %s", exc)
    await db_session.close()


app = FastAPI(
    title="HTQA Event Microservice",
    description="Microservice for receiving and processing HTQA events",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware (order matters - first added is outermost)
app.add_middleware(AuditMiddleware)

# Include routers
app.include_router(events_router)
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
