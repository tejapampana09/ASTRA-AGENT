from __future__ import annotations

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.observability.logging import logger

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = None
AsyncSessionLocal = None
sync_engine = None
SyncSessionLocal = None

try:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )
except Exception as e:
    logger.debug(f"Could not initialize async database engine (expected in offline/unit tests): {e}")

try:
    if settings.DATABASE_URL_SYNC:
        sync_engine = create_engine(
            settings.DATABASE_URL_SYNC,
            echo=False,
            future=True,
            pool_pre_ping=True
        )
        SyncSessionLocal = sessionmaker(
            bind=sync_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
except Exception as e:
    logger.debug(f"Could not initialize sync database engine: {e}")


def get_sync_session_factory():
    """Returns the synchronous sessionmaker if available."""
    return SyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection helper for FastAPI routes."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database engine is not initialized.")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

