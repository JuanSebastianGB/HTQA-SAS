"""SQLAlchemy database models."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, Index, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Timezone-aware UTC now for column defaults."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class EventModel(Base):
    """SQLAlchemy model for events table."""

    __tablename__ = "events"
    __table_args__ = (
        Index(
            "idx_events_severity_occurred_at",
            "severity",
            "occurred_at",
            postgresql_using="btree",
        ),
        # Natural key alignment: source + device + event_type (idempotency in Redis)
        Index(
            "idx_events_source_device_event",
            "source",
            "device_id",
            "event_type",
            postgresql_using="btree",
        ),
        # Customer queries: filter by customer + time range
        Index(
            "idx_events_customer_created",
            "customer_id",
            "created_at",
            postgresql_using="btree",
        ),
        # Critical path: severity filter + ORDER BY occurred_at DESC (partial: critical rows only)
        Index(
            "idx_events_critical_recent",
            "occurred_at",
            postgresql_using="btree",
            postgresql_ops={"occurred_at": "DESC"},
            postgresql_where=text("severity = 'critical'"),
        ),
        {"postgresql_partition_by": "RANGE (occurred_at)"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="low")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class AuditLogModel(Base):
    """SQLAlchemy model for audit_logs table."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid4] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    api_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
