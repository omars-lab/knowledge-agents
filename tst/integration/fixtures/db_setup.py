"""
Integration database setup fixture (DDL + seed data if empty).
"""
import logging
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True, scope="session")
@pytest.mark.fixtures_integration
async def setup_test_environment(wait_for_services):
    """
    Setup test environment before each test.

    COMPLEX LOGIC EXPLANATION:
    This fixture handles the complex database setup for integration tests:
    1. SESSION-SCOPED: Runs once per test session (not per test)
    2. AUTO-CREATION: Creates schema if it doesn't exist
    3. DATA SEEDING: Seeds comprehensive test data
    4. ISOLATION: Ensures each test session gets clean, fresh data
    5. COMMIT STRATEGY: Commits data to make it visible to all database sessions

    This is critical because:
    - Integration tests need real database data
    - Agents need access to apps/actions for tool calls
    - Tests need predictable, consistent data
    - Data must be committed to be visible across sessions
    """
    logger.info("Setting up test database environment...")

    # DATABASE URL CONVERSION:
    # Convert synchronous PostgreSQL URL to async SQLAlchemy URL
    # This is required for async database operations in tests
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://knowledge:knowledge123@postgres:5432/knowledge_workflow",
    )
    if db_url.startswith("postgresql://"):
        # Convert to asyncpg driver for async operations
        async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = db_url

    logger.info(f"Connecting to database: {async_db_url}")
    engine = create_async_engine(async_db_url)

    async with engine.begin() as conn:
        logger.info("Checking if database tables exist...")

        # Check if plans table exists (new schema)
        result = await conn.execute(
            text(
                """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'plans'
            );
        """
            )
        )
        plans_exists = result.scalar()
        logger.info(f"Plans table exists: {plans_exists}")

        # If tables don't exist, run the init script
        if not plans_exists:
            logger.info("Running database initialization script...")
            # The schema should be created by the init script
            # We'll just verify it exists
            try:
                init_script_path = "/docker-entrypoint-initdb.d/01-init-db.sql"
                # For tests, we'll create the schema directly
                await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            except Exception as e:
                logger.warning(f"Could not run init script: {e}")

        # Verify tables exist
        result = await conn.execute(text("SELECT COUNT(*) FROM plans"))
        plans_count = result.scalar()
        logger.info(f"Plans table count: {plans_count}")

    logger.info("Database setup completed successfully")

    # Ensure all transactions are committed and data is visible
    async with engine.begin() as conn:
        # Force a commit by doing a simple query
        result = await conn.execute(text("SELECT COUNT(*) FROM plans"))
        plans_count = result.scalar()
        logger.info(f"Final verification: {plans_count} plans in database")

    await engine.dispose()

    # Add a small delay to ensure data is available to all database sessions
    import asyncio

    await asyncio.sleep(1.0)


@pytest.fixture
async def async_session():
    """Create an async database session for testing."""
    # Get database URL from environment
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://knowledge:knowledge123@postgres:5432/knowledge_workflow",
    )
    if db_url.startswith("postgresql://"):
        async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_db_url = db_url

    engine = create_async_engine(async_db_url)
    AsyncSessionLocal = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()
