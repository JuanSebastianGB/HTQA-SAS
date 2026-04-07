"""Rate limiter service using Redis."""

import logging

import redis.exceptions as redis_exc

from src.application.exceptions import RedisUnavailableError
from src.domain.ports.repository import CacheRepository

logger = logging.getLogger(__name__)


class RateLimiterService:
    """Service for rate limiting API requests (fixed-window counter in Redis)."""

    def __init__(
        self,
        cache_repo: CacheRepository,
        limit: int = 100,
        window_seconds: int = 60,
        *,
        fail_open: bool = True,
    ):
        self._cache = cache_repo
        self._default_limit = limit
        self._window_seconds = window_seconds
        self._fail_open = fail_open

    async def check_limit(self, api_key: str) -> tuple[bool, int]:
        """
        Check if request is within rate limit.
        Returns (is_allowed, current_count).
        """
        key = f"rate_limit:{api_key}"
        try:
            current = await self._cache.increment_with_limit(
                key, self._default_limit, self._window_seconds
            )
        except (RedisUnavailableError, redis_exc.RedisError, OSError):
            if self._fail_open:
                logger.warning(
                    "Rate limit degraded: Redis unavailable; allowing request (fail-open)"
                )
                return True, 0
            raise RedisUnavailableError("Cache service temporarily unavailable") from None
        return current <= self._default_limit, current
