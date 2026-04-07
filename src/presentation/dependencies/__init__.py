# Dependencies package
# Re-export dependencies from auth module for backward compatibility
from .auth import (
    get_redis,
    init_redis,
    get_cache_repo,
    get_db,
    get_event_repo,
    get_notification_port,
    get_severity_classifier,
    get_idempotency_service,
    get_rate_limiter_service,
    get_notification_service,
    get_event_service,
    get_api_key,
)

# Settings
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "your-api-key-here"
    database_url: str = "postgresql+asyncpg://htqa:htqa_pass@postgres:5432/htqa_events"
    redis_url: str = "redis://redis:6379/0"
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    rate_limit_fail_open: bool = True
    idempotency_ttl_seconds: int = 300
    notification_recipient_email: str = "ops@htqa.local"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
