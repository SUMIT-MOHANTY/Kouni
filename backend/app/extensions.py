"""
SQLAlchemy Extensions for LMS Backend Application.

This module configures the async PostgreSQL engine, session maker, and declarative base
for SQLAlchemy 2.0 async operations with connection pooling.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import get_settings

# Get application settings
settings = get_settings()

# Create async PostgreSQL engine with connection pooling
# Using asyncpg driver for native async PostgreSQL support
engine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_pre_ping=True,  # Verify connections before using from pool
    echo=settings.database_echo,
    future=True,  # SQLAlchemy 2.0 style
    # Use NullPool for testing environments to avoid connection issues
    poolclass=NullPool if settings.environment == "testing" else None,
)

# Create async session maker
# expire_on_commit=False keeps objects usable after commit (important for async)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Declarative base for ORM models
# All models will inherit from this base
Base = declarative_base()


async def get_db() -> AsyncSession:
    """
    Dependency injection function to get a database session.
    
    Yields an async database session that is automatically closed
    when the request is complete. Use this as a FastAPI dependency.
    
    Example:
        @app.get("/items/")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    
    Yields:
        AsyncSession: Database session for the request lifecycle
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database by creating all tables.
    
    This should be called during application startup.
    In production, use Alembic migrations instead of create_all.
    
    Note: This creates tables based on models that have been imported.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close database engine and dispose of all connections.
    
    This should be called during application shutdown to ensure
    all connections are properly released.
    """
    await engine.dispose()


async def check_db_connection() -> bool:
    """
    Check if database connection is healthy.
    
    Performs a simple database ping to verify connectivity.
    
    Returns:
        bool: True if database is reachable, False otherwise
    """
    from sqlalchemy import text
    
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        return False
