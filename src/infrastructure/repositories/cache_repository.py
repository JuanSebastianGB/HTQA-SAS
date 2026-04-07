"""Redis cache repository implementation."""

from redis.asyncio import Redis

from src.domain.ports.repository import CacheRepository


class RedisCacheRepository(CacheRepository):
    """Redis implementation of CacheRepository."""

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Set value in cache with TTL."""
        return await self._redis.set(key, value, ex=ttl_seconds)

    async def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Atomically set value only if key does not exist (SETNX + TTL).

        Returns True if the key was set, False if it already existed.
        Uses a single atomic Redis command to prevent race conditions.
        """
        return await self._redis.set(key, value, nx=True, ex=ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        return await self._redis.delete(key) > 0

    async def increment_with_limit(self, key: str, limit: int, window_seconds: int) -> int:
        """
        Atomically increment a per-key counter for a fixed time window (not sliding).

        First request in a window sets TTL; subsequent INCRs share the same window
        until EXPIRE elapses. Uses a Redis Lua script for atomicity.
        """
        # Lua script for atomic increment with expiry
        lua_script = """
        local current = redis.call('INCR', KEYS[1])
        if current == 1 then
            redis.call('EXPIRE', KEYS[1], ARGV[1])
        end
        return current
        """
        result = await self._redis.eval(lua_script, 1, key, window_seconds)
        return int(result)
