"""Idempotency service for preventing duplicate events."""

import redis.exceptions as redis_exc

from src.application.exceptions import RedisUnavailableError
from src.domain.ports.repository import CacheRepository


class IdempotencyService:
    """Service for handling idempotency checks."""

    def __init__(self, cache_repo: CacheRepository, window_seconds: int = 300):
        self._cache = cache_repo
        self._window_seconds = window_seconds

    def _build_key(self, source: str, device_id: str, event_type: str) -> str:
        """Build idempotency key: idempotency:{source}:{device_id}:{event_type}"""
        return f"idempotency:{source}:{device_id}:{event_type}"

    async def check_and_store(
        self,
        source: str,
        device_id: str,
        event_type: str,
        window_seconds: int | None = None,
    ) -> tuple[bool, str | None]:
        """
        Check if event is duplicate and store if not.
        Returns (is_duplicate, existing_event_id).

        Uses atomic SETNX to prevent race conditions under high concurrency.
        """
        key = self._build_key(source, device_id, event_type)

        # Atomic check-and-set: only succeeds if key doesn't exist
        ttl_seconds = window_seconds if window_seconds is not None else self._window_seconds
        try:
            was_set = await self._cache.set_if_not_exists(key, "pending", ttl_seconds)
        except (redis_exc.RedisError, OSError) as exc:
            raise RedisUnavailableError("Cache service temporarily unavailable") from exc

        if not was_set:
            # Key already exists — retrieve the stored value
            try:
                existing = await self._cache.get(key)
            except (redis_exc.RedisError, OSError) as exc:
                raise RedisUnavailableError("Cache service temporarily unavailable") from exc
            return True, existing

        return False, None

    async def mark_completed(
        self, source: str, device_id: str, event_type: str, event_id: str
    ) -> None:
        """Mark idempotency key as completed with event ID."""
        key = self._build_key(source, device_id, event_type)
        try:
            await self._cache.set(key, event_id, self._window_seconds)
        except (redis_exc.RedisError, OSError) as exc:
            raise RedisUnavailableError("Cache service temporarily unavailable") from exc
