"""Repository port interfaces for domain layer."""

from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.event import Event


class EventRepository(ABC):
    """Abstract repository for Event persistence."""

    @abstractmethod
    async def create(self, event: Event) -> Event:
        """Create a new event."""
        pass

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Event | None:
        """Get event by ID."""
        pass

    @abstractmethod
    async def get_critical_last_24h(self) -> list[Event]:
        """Get all critical events from last 24 hours."""
        pass


class CacheRepository(ABC):
    """Abstract repository for Redis cache operations."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Set value in cache with TTL."""
        pass

    @abstractmethod
    async def set_if_not_exists(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Atomically set value only if key does not exist (SETNX + TTL).
        Returns True if the key was set, False if it already existed.
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def increment_with_limit(self, key: str, limit: int, window_seconds: int) -> int:
        """Increment a fixed-window counter; caller compares count to limit."""
        pass


class NotificationServicePort(ABC):
    """Abstract notification service port."""

    @abstractmethod
    async def send(self, recipient: str, subject: str, body: str) -> None:
        """Send notification."""
        pass
