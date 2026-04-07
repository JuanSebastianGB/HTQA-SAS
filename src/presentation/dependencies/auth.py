"""Presentation layer dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.event_service import EventService
from src.application.services.idempotency_service import IdempotencyService
from src.application.services.notification_service import NotificationService
from src.application.services.rate_limiter_service import RateLimiterService
from src.application.services.severity_classifier import SeverityClassifier
from src.infrastructure.database.session import get_db_session
from src.infrastructure.notifications.email_notifier import MockEmailNotifier
from src.infrastructure.repositories.cache_repository import RedisCacheRepository
from src.infrastructure.repositories.event_repository import SQLAlchemyEventRepository

# Redis client - initialized in main.py
_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Get Redis client."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client


def init_redis(
    redis_url: str,
    *,
    socket_connect_timeout: float = 5.0,
    socket_timeout: float = 5.0,
) -> Redis:
    """Initialize Redis client."""
    global _redis_client
    _redis_client = Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=socket_connect_timeout,
        socket_timeout=socket_timeout,
        health_check_interval=30,
    )
    return _redis_client


# Cache repository dependency
def get_cache_repo() -> RedisCacheRepository:
    """Get cache repository."""
    return RedisCacheRepository(get_redis())


# Database session dependency
async def get_db() -> AsyncSession:
    """Get database session."""
    db_session = get_db_session()
    async with db_session.get_session() as session:
        yield session


# Event repository dependency
def get_event_repo() -> type[SQLAlchemyEventRepository]:
    """Get event repository class."""
    return SQLAlchemyEventRepository


# Notification port dependency
def get_notification_port() -> MockEmailNotifier:
    """Get notification port."""
    return MockEmailNotifier()


# Service dependencies
def get_severity_classifier() -> SeverityClassifier:
    """Get severity classifier."""
    return SeverityClassifier()


def get_idempotency_service(
    cache_repo: Annotated[RedisCacheRepository, Depends(get_cache_repo)],
) -> IdempotencyService:
    """Get idempotency service."""
    from src.presentation.dependencies import get_settings

    settings = get_settings()
    return IdempotencyService(
        cache_repo=cache_repo,
        window_seconds=settings.idempotency_ttl_seconds,
    )


def get_rate_limiter_service(
    cache_repo: Annotated[RedisCacheRepository, Depends(get_cache_repo)],
) -> RateLimiterService:
    """Get rate limiter service."""
    from src.presentation.dependencies import get_settings

    settings = get_settings()
    return RateLimiterService(
        cache_repo=cache_repo,
        limit=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
        fail_open=settings.rate_limit_fail_open,
    )


def get_notification_service(
    notifier: Annotated[MockEmailNotifier, Depends(get_notification_port)],
) -> NotificationService:
    """Get notification service."""
    from src.presentation.dependencies import get_settings

    settings = get_settings()
    return NotificationService(
        notifier,
        recipient_email=settings.notification_recipient_email,
    )


async def get_event_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    event_repo_class: Annotated[type[SQLAlchemyEventRepository], Depends(get_event_repo)],
    idempotency_svc: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    rate_limiter_svc: Annotated[RateLimiterService, Depends(get_rate_limiter_service)],
    severity_classifier: Annotated[SeverityClassifier, Depends(get_severity_classifier)],
    notification_svc: Annotated[NotificationService, Depends(get_notification_service)],
) -> EventService:
    """Get event service with all dependencies injected by FastAPI."""
    return EventService(
        event_repo=event_repo_class(db),
        idempotency_svc=idempotency_svc,
        rate_limiter_svc=rate_limiter_svc,
        severity_classifier=severity_classifier,
        notification_svc=notification_svc,
    )


# API Key validation dependency
async def get_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str:
    """Validate API key from header against configured key."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
    # Lazy import to avoid circular dependency with dependencies/__init__.py
    from src.presentation.dependencies import get_settings

    settings = get_settings()
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return x_api_key
