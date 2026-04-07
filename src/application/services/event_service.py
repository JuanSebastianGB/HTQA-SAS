"""Event service - orchestrates event processing."""

import logging
from datetime import datetime
from uuid import UUID

from src.application.dto.event_dto import EventCreateDTO, EventResponseDTO
from src.application.services.idempotency_service import IdempotencyService
from src.application.services.notification_service import NotificationService
from src.application.services.rate_limiter_service import RateLimiterService
from src.application.services.severity_classifier import SeverityClassifier
from src.domain.entities.event import Event
from src.domain.value_objects.event_status import EventStatus
from src.domain.value_objects.severity import Severity

logger = logging.getLogger(__name__)


class EventService:
    """Application service for handling events."""

    def __init__(
        self,
        event_repo: "EventRepository",
        idempotency_svc: IdempotencyService,
        rate_limiter_svc: RateLimiterService,
        severity_classifier: SeverityClassifier,
        notification_svc: NotificationService,
    ):
        self._event_repo = event_repo
        self._idempotency_svc = idempotency_svc
        self._rate_limiter_svc = rate_limiter_svc
        self._severity_classifier = severity_classifier
        self._notification_svc = notification_svc

    async def check_rate_limit(self, api_key: str) -> tuple[bool, int]:
        """Check rate limit for API key."""
        return await self._rate_limiter_svc.check_limit(api_key)

    async def check_idempotency(self, device_id: str, event_type: str) -> tuple[bool, str | None]:
        """Check if event is duplicate."""
        return await self._idempotency_svc.check_and_store(device_id, event_type)

    async def create_event(
        self, dto: EventCreateDTO, background_tasks: "BackgroundTasks"
    ) -> EventResponseDTO:
        """Create a new event with background processing."""
        # Classify severity
        severity = self._severity_classifier.classify(
            dto.event_type, dto.metric_value, dto.metadata
        )

        # Create domain entity
        event = Event(
            source=dto.source,
            customer_id=dto.customer_id,
            device_id=dto.device_id,
            event_type=dto.event_type,
            occurred_at=dto.occurred_at,
            metric_value=dto.metric_value,
            metadata=dto.metadata,
            severity=severity,
            status=EventStatus.PENDING,
        )

        # Persist event
        created_event = await self._event_repo.create(event)

        # Mark idempotency as completed
        await self._idempotency_svc.mark_completed(
            dto.device_id, dto.event_type, str(created_event.id)
        )

        # Schedule background processing for critical events
        if severity == Severity.CRITICAL:
            background_tasks.add_task(self._process_critical_event, created_event.id)

        return self.to_response_dto(created_event)

    async def _process_critical_event(self, event_id: UUID) -> None:
        """Background task to process critical events."""
        event = await self._event_repo.get_by_id(event_id)
        if event and event.severity == Severity.CRITICAL:
            try:
                await self._notification_svc.notify_critical_event(
                    str(event.id),
                    event.device_id,
                    f"Critical event: {event.event_type}",
                )
                event.status = EventStatus.PROCESSED
                await self._event_repo.update(event)
            except Exception as e:
                event.status = EventStatus.FAILED
                await self._event_repo.update(event)
                logger.error(f"Failed to process critical event {event_id}: {e}")

    async def get_critical_events(self, hours: int = 24, limit: int | None = None) -> list[Event]:
        """Get critical events from the last N hours.

        Args:
            hours: Number of hours to look back (default 24)
            limit: Maximum number of events to return (optional)

        Returns:
            List of critical events sorted by occurred_at descending
        """
        return await self._event_repo.get_critical_events(hours=hours, limit=limit)

    def to_response_dto(self, event: Event) -> EventResponseDTO:
        """Convert domain entity to response DTO."""
        return EventResponseDTO(
            id=event.id,
            source=event.source,
            customer_id=event.customer_id,
            device_id=event.device_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            metric_value=event.metric_value,
            metadata=event.metadata,
            severity=event.severity.value,
            status=event.status.value,
            created_at=event.created_at,
        )


# Type alias for BackgroundTasks
from fastapi import BackgroundTasks

EventRepository = "EventRepository"
