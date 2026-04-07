"""PostgreSQL child partitions for RANGE-partitioned `events` (monthly + DEFAULT).

Registers an `after_create` listener so `Base.metadata.create_all` is followed by
idempotent `CREATE TABLE ... PARTITION OF` DDL. Import this module before
`create_all` (see `session.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.schema import DDL

from src.infrastructure.database.models import EventModel


def _month_starts_utc(now: datetime) -> tuple[datetime, datetime, datetime]:
    """Return UTC starts of current month, next month, and month after next."""
    now = now.astimezone(UTC) if now.tzinfo else now.replace(tzinfo=UTC)
    y, m = now.year, now.month
    start_current = datetime(y, m, 1, tzinfo=UTC)
    start_next = _add_months(start_current, 1)
    start_after = _add_months(start_next, 1)
    return start_current, start_next, start_after


def _add_months(dt: datetime, months: int) -> datetime:
    """Add calendar months in UTC (dt must be timezone-aware UTC)."""
    y, m = dt.year, dt.month + months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return datetime(y, m, 1, tzinfo=UTC)


def _partition_table_name(prefix: str, dt: datetime) -> str:
    return f"{prefix}_{dt.year:04d}_{dt.month:02d}"


def _relation_exists(connection: Connection, schema: str, relname: str) -> bool:
    row = connection.execute(
        text("""
            SELECT 1
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
              AND c.relname = :relname
            """),
        {"schema": schema, "relname": relname},
    ).scalar()
    return row is not None


def _create_month_partition(
    connection: Connection,
    schema: str,
    parent: str,
    part_name: str,
    start: datetime,
    end: datetime,
) -> None:
    if _relation_exists(connection, schema, part_name):
        return
    start_s = start.isoformat()
    end_s = end.isoformat()
    ddl = (
        f"CREATE TABLE {schema}.{part_name} PARTITION OF {schema}.{parent} "
        f"FOR VALUES FROM ('{start_s}') TO ('{end_s}')"
    )
    connection.execute(DDL(ddl))


def _create_default_partition(
    connection: Connection, schema: str, parent: str, part_name: str
) -> None:
    if _relation_exists(connection, schema, part_name):
        return
    ddl = f"CREATE TABLE {schema}.{part_name} PARTITION OF {schema}.{parent} DEFAULT"
    connection.execute(DDL(ddl))


@event.listens_for(EventModel.__table__, "after_create")
def _create_event_partitions(target: Any, connection: Connection, **kw: Any) -> None:
    schema = target.schema or "public"
    parent = EventModel.__tablename__
    prefix = f"{parent}_p"

    start_current, start_next, start_after = _month_starts_utc(datetime.now(UTC))

    _create_month_partition(
        connection,
        schema,
        parent,
        _partition_table_name(prefix, start_current),
        start_current,
        start_next,
    )
    _create_month_partition(
        connection,
        schema,
        parent,
        _partition_table_name(prefix, start_next),
        start_next,
        start_after,
    )
    _create_default_partition(connection, schema, parent, f"{parent}_default")
