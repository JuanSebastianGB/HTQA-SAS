"""EventStatus value object."""

from enum import Enum


class EventStatus(str, Enum):
    """Status of an event in the system."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"

    def is_terminal(self) -> bool:
        """Check if status is terminal (no further processing)."""
        return self in (self.PROCESSED, self.FAILED)
