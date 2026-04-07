"""Pytest configuration and fixtures."""

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from src.domain.entities.event import Event
from src.domain.value_objects.severity import Severity
from src.domain.value_objects.event_status import EventStatus


@pytest.fixture
def sample_event():
    """Create a sample event for testing."""
    return Event(
        source="test-source",
        customer_id="customer-1",
        device_id="device-1",
        event_type="test_event",
        occurred_at=datetime.now(UTC),
        metric_value=50.0,
        metadata={"test": "data"},
    )


@pytest.fixture
def critical_event():
    """Create a critical event for testing."""
    return Event(
        source="sensor-1",
        customer_id="cust-123",
        device_id="device-456",
        event_type="error",
        occurred_at=datetime.now(UTC),
        metric_value=150.0,
        severity=Severity.CRITICAL,
        status=EventStatus.PENDING,
    )


@pytest.fixture
def mock_cache_repository():
    """Create a mock cache repository."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.set_if_not_exists = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=True)
    mock.increment_with_limit = AsyncMock(return_value=1)
    return mock


@pytest.fixture
def mock_event_repository():
    """Create a mock event repository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_critical_last_24h = AsyncMock(return_value=[])
    mock.update = AsyncMock()
    return mock


@pytest.fixture
def mock_notification_port():
    """Create a mock notification port."""
    mock = MagicMock()
    mock.send = AsyncMock()
    return mock
