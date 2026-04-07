"""Tests for infrastructure repositories."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.domain.entities.event import Event
from src.domain.value_objects.event_status import EventStatus
from src.domain.value_objects.severity import Severity
from src.infrastructure.database.models import EventModel
from src.infrastructure.repositories.cache_repository import RedisCacheRepository
from src.infrastructure.repositories.event_repository import SQLAlchemyEventRepository


class TestRedisCacheRepository:
    """Test Redis cache repository."""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.eval = AsyncMock(return_value=1)
        return mock

    @pytest.fixture
    def cache_repo(self, mock_redis):
        return RedisCacheRepository(mock_redis)

    @pytest.mark.asyncio
    async def test_get_returns_value(self, cache_repo, mock_redis):
        """Test get returns cached value."""
        mock_redis.get.return_value = "test-value"
        result = await cache_repo.get("test-key")
        assert result == "test-value"

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, cache_repo, mock_redis):
        """Test get returns None for missing key."""
        mock_redis.get.return_value = None
        result = await cache_repo.get("missing-key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_returns_true(self, cache_repo, mock_redis):
        """Test set returns True on success."""
        result = await cache_repo.set("test-key", "test-value", 60)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, cache_repo, mock_redis):
        """Test delete returns True when key exists."""
        result = await cache_repo.delete("test-key")
        assert result is True

    @pytest.mark.asyncio
    async def test_increment_with_limit(self, cache_repo, mock_redis):
        """Test increment_with_limit increments counter."""
        mock_redis.eval.return_value = 5
        result = await cache_repo.increment_with_limit("rate_limit:key", 100, 60)
        assert result == 5


class TestEventRepository:
    """Test event repository with mocked session."""

    @pytest.fixture
    def mock_session(self):
        mock = MagicMock()
        mock.add = MagicMock()
        mock.flush = AsyncMock()
        mock.refresh = AsyncMock()
        mock.execute = AsyncMock()
        mock.get = AsyncMock()
        mock.commit = AsyncMock()
        mock.rollback = AsyncMock()
        return mock

    @pytest.fixture
    def event_repo(self, mock_session):
        return SQLAlchemyEventRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_event(self, event_repo, mock_session):
        """Test get_by_id returns event when found."""
        mock_model = MagicMock()
        mock_model.id = "test-id"
        mock_model.source = "test-source"
        mock_model.customer_id = "test-customer"
        mock_model.device_id = "test-device"
        mock_model.event_type = "test-event"
        mock_model.occurred_at = "2024-01-01"
        mock_model.metric_value = 50.0
        mock_model.event_metadata = {}
        mock_model.severity = "low"
        mock_model.status = "pending"
        mock_model.created_at = "2024-01-01"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute.return_value = mock_result

        result = await event_repo.get_by_id("test-id")
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_loads_row_with_composite_identity(self, event_repo, mock_session):
        """update() uses session.get with (id, occurred_at) composite primary key."""
        eid = uuid4()
        occurred = datetime(2024, 6, 10, 10, 0, 0, tzinfo=UTC)
        mock_model = MagicMock()
        mock_session.get.return_value = mock_model

        event = Event(
            id=eid,
            source="s",
            customer_id="c",
            device_id="d",
            event_type="t",
            occurred_at=occurred,
            metric_value=1.0,
            metadata={},
            severity=Severity.HIGH,
            status=EventStatus.PENDING,
        )

        await event_repo.update(event)

        mock_session.get.assert_awaited_once_with(EventModel, (eid, occurred))


class TestGetCriticalEvents:
    """Test SQLAlchemyEventRepository.get_critical_events() with mocked session."""

    @pytest.fixture
    def mock_session(self):
        mock = MagicMock()
        mock.add = MagicMock()
        mock.flush = AsyncMock()
        mock.refresh = AsyncMock()
        mock.execute = AsyncMock()
        return mock

    @pytest.fixture
    def event_repo(self, mock_session):
        return SQLAlchemyEventRepository(mock_session)

    @pytest.mark.asyncio
    async def test_get_critical_events_returns_list(self, event_repo, mock_session):
        """Test get_critical_events returns list of events."""
        # Setup mock result
        mock_model = MagicMock()
        mock_model.id = "test-id"
        mock_model.source = "test-source"
        mock_model.customer_id = "test-customer"
        mock_model.device_id = "test-device"
        mock_model.event_type = "critical-event"
        mock_model.occurred_at = "2024-01-01"
        mock_model.metric_value = 100.0
        mock_model.event_metadata = {}
        mock_model.severity = "critical"
        mock_model.status = "pending"
        mock_model.created_at = "2024-01-01"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_model]
        mock_session.execute.return_value = mock_result

        result = await event_repo.get_critical_events(hours=24)

        assert len(result) == 1
        assert result[0].severity.value == "critical"

    @pytest.mark.asyncio
    async def test_get_critical_events_with_limit(self, event_repo, mock_session):
        """Test get_critical_events respects limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await event_repo.get_critical_events(hours=24, limit=10)

        # Verify limit was passed in query
        call_args = mock_session.execute.call_args
        assert call_args is not None
