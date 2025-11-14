#!/usr/bin/env python3
"""
Seed PostgreSQL Database with Plans, Buckets, and Tasks from NotePlan Files

PURPOSE: Populate PostgreSQL database with Plans, Buckets, and Tasks parsed from NotePlan markdown files
SCOPE: Read NotePlan files, parse markdown structure, create Plans/Buckets/Tasks with proper hierarchy

This script:
- Iterates through NotePlan files in /noteplan directory
- Identifies daily plan files (typically YYYY-MM-DD.md format)
- Parses markdown to HTML for better structure extraction
- Creates Plan records for daily plans
- Creates Bucket records for markdown sections (h1, h2, h3, etc.)
- Creates Task records for markdown todos, properly referencing bucket hierarchy
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from knowledge_agents.config.api_config import Settings
from knowledge_agents.config.logging_config import setup_logging
from knowledge_agents.database.models import Bucket, Plan, Task
from notes.parser import parse_markdown_to_structure, read_noteplan_file
from notes.traversal import get_daily_plan_files

# Configure logging using centralized config
setup_logging()
logger = logging.getLogger(__name__)

# NotePlan directory path in container
NOTEPLAN_DIR = Path("/noteplan")


async def seed_database_from_noteplan() -> None:
    """Main function to seed the database from NotePlan files."""
    logger.info("Starting database seeding process from NotePlan files")

    try:
        # Initialize Settings (explicit dependency injection pattern)
        settings = Settings()
        db_url = settings.database_url

        # Convert to async SQLAlchemy URL
        if db_url.startswith("postgresql://"):
            async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_db_url = db_url

        logger.info(f"Connecting to database: {async_db_url}")

        engine = create_async_engine(async_db_url)
        async_session = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        # Get daily plan files
        daily_plans = get_daily_plan_files(NOTEPLAN_DIR)

        if not daily_plans:
            logger.warning("No daily plan files found. Nothing to seed.")
            return

        async with async_session() as session:
            plans_created = 0
            buckets_created = 0
            tasks_created = 0

            for file_path, plan_date in daily_plans:
                try:
                    # Read file content
                    content = read_noteplan_file(file_path)

                    logger.info(
                        f"Processing daily plan: {file_path.name} (date: {plan_date.date()})"
                    )

                    # Parse markdown structure
                    structure = parse_markdown_to_structure(content)

                    # Create Plan record
                    plan = Plan(
                        title=f"Daily Plan - {plan_date.strftime('%Y-%m-%d')}",
                        description=f"Daily plan from {file_path.name}",
                        plan_type="daily",
                        plan_date=plan_date.date(),
                    )
                    session.add(plan)
                    await session.flush()  # Flush to get the ID
                    plan_id = plan.id
                    plans_created += 1
                    logger.debug(f"Created plan with ID: {plan_id}")

                    # Create Bucket records for sections
                    section_id_to_bucket_id = {}  # Map section_id -> bucket_id
                    order_index = 0

                    for section in structure["sections"]:
                        bucket = Bucket(
                            plan_id=plan_id,
                            name=section["text"],
                            description=f"Section level {section['level']}",
                            order_index=order_index,
                        )
                        session.add(bucket)
                        await session.flush()  # Flush to get the ID
                        bucket_id = bucket.id
                        section_id_to_bucket_id[section["id"]] = bucket_id
                        buckets_created += 1
                        order_index += 1
                        logger.debug(
                            f"Created bucket: {section['text']} (ID: {bucket_id})"
                        )

                    # Create Task records for todos
                    # Tasks are associated with ALL parent buckets in the hierarchy
                    # If a task is under h3, create task records for h1, h2, and h3 buckets
                    task_order_index = 0

                    for todo in structure["todos"]:
                        # Get all buckets in hierarchy (h1, h2, h3, etc.)
                        # Tasks should be associated with all parent buckets
                        bucket_ids = []
                        bucket_sections = []  # Store section info for each bucket
                        if todo["section_ids"]:
                            # Get all section IDs that have buckets (in hierarchy order)
                            for section_id in todo["section_ids"]:
                                if section_id in section_id_to_bucket_id:
                                    bucket_ids.append(
                                        section_id_to_bucket_id[section_id]
                                    )
                                    # Find the section info
                                    for section in structure["sections"]:
                                        if section["id"] == section_id:
                                            bucket_sections.append(section)
                                            break

                        # Determine status
                        status = "completed" if todo["completed"] else "pending"

                        # Create task record for EACH bucket in the hierarchy
                        # This ensures tasks are tagged/appear in all parent buckets
                        if bucket_ids:
                            for bucket_idx, bucket_id in enumerate(bucket_ids):
                                # Build description with full hierarchy context
                                section_texts = []
                                for section in bucket_sections[
                                    : bucket_idx + 1
                                ]:  # Include up to current level
                                    section_texts.append(
                                        f"{'#' * section['level']} {section['text']}"
                                    )

                                # For tasks in parent buckets, note they're from nested sections
                                context_note = ""
                                if bucket_idx < len(bucket_ids) - 1:
                                    deepest_section = bucket_sections[-1]
                                    context_note = (
                                        f"\n(Originally from {deepest_section['text']})"
                                    )

                                task = Task(
                                    bucket_id=bucket_id,
                                    title=todo["text"],
                                    description=f"Task from sections:\n"
                                    + "\n".join(section_texts)
                                    + context_note
                                    if section_texts
                                    else "Task with no parent sections",
                                    status=status,
                                    order_index=task_order_index,
                                )
                                session.add(task)
                                await session.flush()  # Flush to get the ID
                                task_id = task.id
                                tasks_created += 1
                                logger.debug(
                                    f"Created task: {todo['text']} (ID: {task_id}, bucket: {bucket_id}, level: {bucket_sections[bucket_idx]['level']})"
                                )
                        else:
                            # Task with no sections - create in plan root
                            task = Task(
                                bucket_id=None,  # No bucket - at plan root
                                title=todo["text"],
                                description="Task with no parent sections",
                                status=status,
                                order_index=task_order_index,
                            )
                            session.add(task)
                            await session.flush()  # Flush to get the ID
                            task_id = task.id
                            tasks_created += 1
                            logger.debug(
                                f"Created task: {todo['text']} (ID: {task_id}, no bucket)"
                            )

                        task_order_index += 1

                    # Commit after each plan to avoid huge transactions
                    await session.commit()
                    logger.info(
                        f"✅ Completed processing {file_path.name}: {plans_created} plans, {buckets_created} buckets, {tasks_created} tasks"
                    )

                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    await session.rollback()
                    continue

            logger.info(
                f"✅ Database seeding completed: {plans_created} plans, {buckets_created} buckets, {tasks_created} tasks total"
            )

    except Exception as e:
        logger.error(f"❌ Error seeding database: {e}")
        raise


def main():
    """Entry point for the script."""
    try:
        asyncio.run(seed_database_from_noteplan())
        logger.info("Database seeding completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
