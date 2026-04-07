"""Application-level exceptions (cross-cutting concerns)."""


class RedisUnavailableError(Exception):
    """Raised when Redis operations fail after retries (dependency unavailable)."""
