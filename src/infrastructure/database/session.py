"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.infrastructure.database.models import Base

# Register partition DDL listeners before create_all (side-effect import).
from src.infrastructure.database import partition_ddl  # noqa: F401

# Default URLs - override via environment
DEFAULT_DATABASE_URL = "postgresql+asyncpg://htqa:htqa_pass@postgres:5432/htqa_events"


class DatabaseSession:
    """Manages database sessions."""

    def __init__(self, database_url: str = DEFAULT_DATABASE_URL):
        self._engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def create_tables(self) -> None:
        """Create all tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all tables."""
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async session context manager."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Close engine."""
        await self._engine.dispose()


# Global instance - initialized in main.py
_db_session: DatabaseSession | None = None


def get_db_session() -> DatabaseSession:
    """Get global database session instance."""
    if _db_session is None:
        raise RuntimeError("Database session not initialized")
    return _db_session


def init_db_session(database_url: str) -> DatabaseSession:
    """Initialize global database session."""
    global _db_session
    _db_session = DatabaseSession(database_url)
    return _db_session
