"""Application layer DTOs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreateDTO(BaseModel):
    """DTO for creating an event."""

    source: str = Field(..., min_length=1, max_length=100)
    customer_id: str = Field(..., min_length=1, max_length=100)
    device_id: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., min_length=1, max_length=100)
    occurred_at: datetime
    metric_value: float
    metadata: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class EventResponseDTO(BaseModel):
    """DTO for event response."""

    id: UUID
    source: str
    customer_id: str
    device_id: str
    event_type: str
    occurred_at: datetime
    metric_value: float
    metadata: dict[str, str]
    severity: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
