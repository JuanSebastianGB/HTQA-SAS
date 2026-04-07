"""Event repository implementation using SQLAlchemy."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.event import Event
from src.domain.ports.repository import EventRepository
from src.domain.value_objects.event_status import EventStatus
from src.domain.value_objects.severity import Severity
from src.infrastructure.database.models import EventModel


class SQLAlchemyEventRepository(EventRepository):
    """SQLAlchemy implementation of EventRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_domain(self, model: EventModel) -> Event:
        """Convert database model to domain entity."""
        return Event(
            id=model.id,
            source=model.source,
            customer_id=model.customer_id,
            device_id=model.device_id,
            event_type=model.event_type,
            occurred_at=model.occurred_at,
            metric_value=model.metric_value,
            metadata=model.event_metadata or {},
            severity=Severity(model.severity),
            status=EventStatus(model.status),
            created_at=model.created_at,
        )

    def _to_model(self, event: Event) -> EventModel:
        """Convert domain entity to database model."""
        return EventModel(
            id=event.id,
            source=event.source,
            customer_id=event.customer_id,
            device_id=event.device_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            metric_value=event.metric_value,
            event_metadata=event.metadata,
            severity=event.severity.value,
            status=event.status.value,
            created_at=event.created_at,
        )

    async def create(self, event: Event) -> Event:
        """Create a new event."""
        model = self._to_model(event)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, event_id: UUID) -> Event | None:
        """Get event by ID."""
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_critical_events(self, hours: int = 24, limit: int | None = None) -> list[Event]:
        """Get critical events from the last N hours.

        Args:
            hours: Number of hours to look back (default 24)
            limit: Maximum number of events to return (optional)

        Returns:
            List of critical events sorted by occurred_at descending
        """

        since = datetime.now(UTC) - timedelta(hours=hours)
        query = (
            select(EventModel)
            .where(EventModel.severity == Severity.CRITICAL.value)
            .where(EventModel.occurred_at >= since)
            .order_by(EventModel.occurred_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_critical_last_24h(self) -> list[Event]:
        """Get all critical events from last 24 hours."""
        return await self.get_critical_events(hours=24)

    async def update(self, event: Event) -> Event:
        """Update an existing event."""
        model = await self._session.get(EventModel, (event.id, event.occurred_at))
        if model:
            model.severity = event.severity.value
            model.status = event.status.value
            model.event_metadata = event.metadata
            await self._session.flush()
            await self._session.refresh(model)
            return self._to_domain(model)
        raise ValueError(f"Event {event.id} not found")
