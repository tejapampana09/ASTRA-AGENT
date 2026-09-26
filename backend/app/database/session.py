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
        echo=False,
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
    import socket
    # Fast 0.2s socket check before attempting PostgreSQL connection
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        s.connect(("127.0.0.1", 5432))

    _test_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=False,
        future=True,
        pool_pre_ping=True,
    )
    with _test_engine.connect() as conn:
        pass
    sync_engine = _test_engine
    SyncSessionLocal = sessionmaker(
        bind=sync_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False
    )
except Exception:
    # Instant fallback to local SQLite for durable tasks and event persistence
    from pathlib import Path
    db_file = Path(__file__).resolve().parent.parent.parent / "astra.db"
    sqlite_url = f"sqlite:///{db_file}"
    try:
        sqlite_engine = create_engine(sqlite_url, echo=False, connect_args={"check_same_thread": False})
        sync_engine = sqlite_engine
        SyncSessionLocal = sessionmaker(bind=sqlite_engine, autocommit=False, autoflush=False)
    except Exception as e:
        sync_engine = None
        SyncSessionLocal = None


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

