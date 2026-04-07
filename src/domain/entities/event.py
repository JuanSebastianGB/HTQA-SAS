from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.value_objects.severity import Severity
from src.domain.value_objects.event_status import EventStatus


def _utcnow() -> datetime:
    """Timezone-aware UTC now for dataclass defaults."""
    return datetime.now(UTC)


@dataclass
class Event:
    """Event entity - core domain model."""

    id: UUID = field(default_factory=uuid4)
    source: str = ""
    customer_id: str = ""
    device_id: str = ""
    event_type: str = ""
    occurred_at: datetime = field(default_factory=_utcnow)
    metric_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.LOW
    status: EventStatus = EventStatus.PENDING
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self):
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity)
        if isinstance(self.status, str):
            self.status = EventStatus(self.status)
