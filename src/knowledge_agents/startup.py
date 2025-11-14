"""Startup logic for the Agentic API."""

import logging
import time

from agents import set_default_openai_client
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine as sqlalchemy_create_async_engine

from .config.api_config import Settings
from .dependencies import Dependencies

logger = logging.getLogger(__name__)


async def check_database_connection(settings: Settings, metrics) -> bool:
    """
    Test database connection.

    Args:
        settings: Application settings instance
        metrics: Metrics instance
    """
    start_time = time.time()
    try:
        # Create engine directly with proper URL
        # Get the database URL and convert to async
        db_url = settings.database_url
        if db_url.startswith("postgresql://"):
            async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_db_url = db_url

        engine = sqlalchemy_create_async_engine(
            async_db_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,
            echo=settings.debug,
        )

        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            logger.info(f"Database connection successful: {row}")

        # Close the engine
        await engine.dispose()

        # Record successful connection metrics
        duration = time.time() - start_time
        metrics.db_connections_total.labels(status="success").inc()
        metrics.db_connection_duration.observe(duration)
        logger.info("Database connection successful")
        return True

    except Exception as e:
        # Record failed connection metrics
        duration = time.time() - start_time
        metrics.db_connections_total.labels(status="failure").inc()
        metrics.db_connection_duration.observe(duration)
        logger.error(f"Database connection failed: {e}")
        return False


async def startup_tasks(dependencies: Dependencies, metrics) -> bool:
    """
    Startup tasks.

    Args:
        dependencies: Dependencies container (required)
        metrics: Metrics instance
    """
    settings = dependencies.settings

    logger.info(f"Starting Agentic API in {settings.environment} mode...")
    logger.info(f"Database URL: {settings.database_url}")

    # Record service start metrics
    metrics.service_starts_total.inc()

    # Wire default OpenAI client for the agents framework using our managed client
    try:
        client = dependencies.openai_client
        set_default_openai_client(client)
        logger.info("Default OpenAI client configured for agents framework")
    except Exception as e:
        logger.error(f"Failed to configure default OpenAI client: {e}")

    # Test database connection
    db_connected = await check_database_connection(settings, metrics)

    # Metrics will be exposed via FastAPI /metrics endpoint
    logger.info("Metrics will be exposed via /metrics endpoint")

    logger.info("Agentic API ready!")
    return db_connected
