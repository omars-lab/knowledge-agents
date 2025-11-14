"""Database session utilities."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine as sqlalchemy_create_async_engine

from ..metrics import metrics
from ..types.exceptions import DatabaseError

if TYPE_CHECKING:
    from ..config.api_config import Settings


def get_database_url(settings: "Settings") -> str:
    """
    Get database URL from settings.

    Args:
        settings: Settings instance (required)

    Returns:
        Database connection URL string
    """
    return settings.database_url


def get_async_database_url(settings: "Settings") -> str:
    """
    Get async database URL from settings.

    Args:
        settings: Settings instance (required)

    Returns:
        Async database connection URL string
    """
    db_url = get_database_url(settings)
    # Convert postgresql:// to postgresql+asyncpg://
    if db_url.startswith("postgresql://"):
        return db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return db_url


def get_async_engine(settings: "Settings") -> AsyncEngine:
    """
    Create asynchronous database engine with connection pooling.

    Args:
        settings: Settings instance (required)

    Returns:
        AsyncEngine instance

    Raises:
        DatabaseError: If engine creation fails
    """
    try:
        return sqlalchemy_create_async_engine(
            get_async_database_url(settings),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,  # Verify connections before use
            echo=settings.debug,  # Log SQL queries in debug mode
        )
    except Exception as e:
        raise DatabaseError(f"Failed to create async database engine: {e}")


def get_async_session(settings: "Settings") -> AsyncSession:
    """
    Get asynchronous database session.

    Args:
        settings: Settings instance (required)

    Returns:
        AsyncSession instance

    Raises:
        DatabaseError: If session creation fails
    """
    try:
        engine = get_async_engine(settings)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        # Record successful database connection
        metrics.db_connections_total.labels(status="success").inc()
        return AsyncSessionLocal()
    except Exception as e:
        # Record failed database connection
        metrics.db_connections_total.labels(status="error").inc()
        raise DatabaseError(f"Failed to create async session: {e}")


# def create_sync_engine() -> Engine:
#     """Create synchronous database engine with connection pooling."""
#     try:
#         return create_engine(
#             get_database_url(),
#             poolclass=QueuePool,
#             pool_size=settings.db_pool_size,
#             max_overflow=settings.db_max_overflow,
#             pool_timeout=settings.db_pool_timeout,
#             pool_pre_ping=True,  # Verify connections before use
#             echo=settings.debug,  # Log SQL queries in debug mode
#         )
#     except Exception as e:
#         raise DatabaseError(f"Failed to create sync database engine: {e}")


# def get_sync_session() -> Session:
#     """Get synchronous database session."""
#     try:
#         engine = create_sync_engine()
#         SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#         return SessionLocal()
#     except Exception as e:
#         raise DatabaseError(f"Failed to create sync session: {e}")
