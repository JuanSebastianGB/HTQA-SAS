"""Audit log repository implementation using SQLAlchemy."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models import AuditLogModel


class AuditLogRepository:
    """Repository for audit log persistence and querying."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(
        self,
        timestamp: datetime,
        api_key: str | None,
        method: str,
        path: str,
        status_code: int,
        ip_address: str | None,
    ) -> AuditLogModel:
        """Create and persist an audit log entry."""
        audit_record = AuditLogModel(
            timestamp=timestamp,
            api_key=api_key,
            method=method,
            path=path,
            status_code=status_code,
            ip_address=ip_address,
        )
        self._session.add(audit_record)
        await self._session.flush()
        await self._session.refresh(audit_record)
        return audit_record

    async def get_by_path(self, path: str, limit: int = 100) -> list[AuditLogModel]:
        """Get audit logs filtered by path."""
        result = await self._session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.path.like(f"%{path}%"))
            .order_by(AuditLogModel.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_timerange(
        self,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> list[AuditLogModel]:
        """Get audit logs within a time range."""
        result = await self._session.execute(
            select(AuditLogModel)
            .where(AuditLogModel.timestamp >= start)
            .where(AuditLogModel.timestamp <= end)
            .order_by(AuditLogModel.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
