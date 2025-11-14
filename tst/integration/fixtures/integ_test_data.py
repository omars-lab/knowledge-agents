"""
Reusable integration test data helpers.

Centralized async utilities for clearing and seeding the database with
NotePlan data (Plans, Buckets, Tasks) used across integration tests.
"""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest
from sqlalchemy import delete, insert

from knowledge_agents.config.api_config import Settings
from knowledge_agents.database.models import Bucket, Plan, Task
from knowledge_agents.database.sessions import get_async_session

logger = logging.getLogger(__name__)


async def clear_all_data() -> None:
    """Delete all rows from tasks, buckets, and plans tables (in that order to respect foreign keys)."""
    settings = Settings()
    db = get_async_session(settings=settings)
    try:
        # Check if tables exist before trying to delete from them
        # If tables don't exist, that's fine - they'll be created by db-seed
        from sqlalchemy import text
        from sqlalchemy.exc import ProgrammingError

        try:
            await db.execute(delete(Task))
            await db.execute(delete(Bucket))
            await db.execute(delete(Plan))
            await db.commit()
        except ProgrammingError as e:
            # If tables don't exist, ignore the error
            if "does not exist" in str(e):
                logger.debug("Tables don't exist yet, skipping cleanup")
                await db.rollback()
            else:
                raise
    finally:
        await db.close()


async def seed_comprehensive_noteplan_data() -> None:
    """Seed comprehensive NotePlan test data with Plans, Buckets, and Tasks."""
    settings = Settings()
    db = get_async_session(settings=settings)
    try:
        # Create a daily plan
        plan_result = await db.execute(
            insert(Plan)
            .values(
                title="Daily Plan 2025-01-15",
                description="Test daily plan",
                plan_type="daily",
                plan_date=date(2025, 1, 15),
            )
            .returning(Plan.id)
        )
        plan_id = plan_result.scalar_one()

        # Create buckets (sections)
        bucket1_result = await db.execute(
            insert(Bucket)
            .values(
                plan_id=plan_id,
                name="Morning Tasks",
                description="Tasks for the morning",
                order_index=0,
            )
            .returning(Bucket.id)
        )
        bucket1_id = bucket1_result.scalar_one()

        bucket2_result = await db.execute(
            insert(Bucket)
            .values(
                plan_id=plan_id,
                name="Work Tasks",
                description="Work-related tasks",
                order_index=1,
            )
            .returning(Bucket.id)
        )
        bucket2_id = bucket2_result.scalar_one()

        # Create tasks
        await db.execute(
            insert(Task).values(
                bucket_id=bucket1_id,
                title="Go to gym",
                description="Morning workout",
                status="pending",
                order_index=0,
            )
        )

        await db.execute(
            insert(Task).values(
                bucket_id=bucket1_id,
                title="Breakfast",
                description="Have breakfast",
                status="completed",
                order_index=1,
            )
        )

        await db.execute(
            insert(Task).values(
                bucket_id=bucket2_id,
                title="Review PRs",
                description="Review pull requests",
                status="pending",
                order_index=0,
            )
        )

        await db.execute(
            insert(Task).values(
                bucket_id=bucket2_id,
                title="Standup meeting",
                description="Daily standup",
                status="completed",
                order_index=1,
            )
        )

        # Create a task at plan root (no bucket)
        await db.execute(
            insert(Task).values(
                bucket_id=None,
                title="Root level task",
                description="Task at plan root",
                status="pending",
                order_index=0,
            )
        )

        await db.commit()
        logger.info("Seeded comprehensive NotePlan test data")
    finally:
        await db.close()


@pytest.fixture
async def setup_test_environment():
    """Fixture to set up test environment with comprehensive NotePlan data."""
    await clear_all_data()
    await seed_comprehensive_noteplan_data()
    yield
    # Cleanup happens automatically via clear_all_data in next test


@pytest.fixture
async def dataset_comprehensive():
    """Fixture to seed comprehensive NotePlan dataset."""
    await clear_all_data()
    await seed_comprehensive_noteplan_data()
    yield
