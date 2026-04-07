"""Severity value object."""

from enum import Enum


class Severity(str, Enum):
    """Severity levels for events."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """Create Severity from string, defaulting to LOW if invalid."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.LOW
