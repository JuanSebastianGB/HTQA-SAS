"""Unit tests for Event entity."""

from datetime import UTC, datetime
from uuid import UUID

from src.domain.entities.event import Event
from src.domain.value_objects.severity import Severity
from src.domain.value_objects.event_status import EventStatus


class TestEventEntity:
    """Test suite for Event entity."""

    def test_create_event_with_defaults(self):
        """Test creating event with default values."""
        event = Event(
            source="test-source",
            customer_id="customer-1",
            device_id="device-1",
            event_type="temperature_high",
            occurred_at=datetime.now(UTC),
            metric_value=85.5,
        )

        assert event.source == "test-source"
        assert event.customer_id == "customer-1"
        assert event.device_id == "device-1"
        assert event.event_type == "temperature_high"
        assert event.metric_value == 85.5
        assert event.severity == Severity.LOW
        assert event.status == EventStatus.PENDING
        assert event.id is not None
        assert event.created_at is not None

    def test_create_event_with_custom_values(self):
        """Test creating event with custom severity and status."""
        occurred_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event = Event(
            source="sensor-1",
            customer_id="cust-123",
            device_id="dev-456",
            event_type="error",
            occurred_at=occurred_at,
            metric_value=100.0,
            severity=Severity.CRITICAL,
            status=EventStatus.PROCESSED,
            metadata={"location": "building-a"},
        )

        assert event.severity == Severity.CRITICAL
        assert event.status == EventStatus.PROCESSED
        assert event.metadata == {"location": "building-a"}

    def test_event_string_severity_conversion(self):
        """Test conversion from string to Severity enum."""
        event = Event(
            source="test",
            customer_id="test",
            device_id="test",
            event_type="test",
            occurred_at=datetime.now(UTC),
            metric_value=0,
            severity="high",
        )
        assert event.severity == Severity.HIGH

    def test_event_string_status_conversion(self):
        """Test conversion from string to EventStatus enum."""
        event = Event(
            source="test",
            customer_id="test",
            device_id="test",
            event_type="test",
            occurred_at=datetime.now(UTC),
            metric_value=0,
            status="failed",
        )
        assert event.status == EventStatus.FAILED

    def test_event_id_is_uuid(self):
        """Test that event ID is a valid UUID."""
        event = Event(
            source="test",
            customer_id="test",
            device_id="test",
            event_type="test",
            occurred_at=datetime.now(UTC),
            metric_value=0,
        )
        assert isinstance(event.id, UUID)

    def test_event_equality_by_id(self):
        """Test event equality is based on ID."""
        event1 = Event(
            source="test",
            customer_id="test",
            device_id="test",
            event_type="test",
            occurred_at=datetime.now(UTC),
            metric_value=0,
        )
        event2 = Event(
            source="test",
            customer_id="test",
            device_id="test",
            event_type="test",
            occurred_at=datetime.now(UTC),
            metric_value=0,
        )
        # Different IDs means different events
        assert event1.id != event2.id
