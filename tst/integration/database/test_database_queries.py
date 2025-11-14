"""
Integration tests for database query functions (real database connections).
"""
from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_agents.database.models import Bucket, Plan, Task
from knowledge_agents.database.queries.query_buckets import BucketQueries
from knowledge_agents.database.queries.query_plans import PlanQueries
from knowledge_agents.database.queries.query_tasks import TaskQueries

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


class TestPlanQueries:
    """Test plan query functions with real database connections."""

    async def test_create_and_get_plan(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test creating and retrieving a plan."""
        # Create a plan
        plan = Plan(
            title="Test Daily Plan",
            description="Test description",
            plan_type="daily",
            plan_date=date.today(),
        )
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        # Query it
        plan_queries = PlanQueries(async_session)
        result = await plan_queries.get_plan_by_id(plan.id)

        assert result is not None
        assert result.title == "Test Daily Plan"
        assert result.plan_type == "daily"
        assert result.plan_date == date.today()

    async def test_get_plans_by_type(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test getting plans by type."""
        # Create daily and goal plans
        daily_plan = Plan(title="Daily Plan", plan_type="daily", plan_date=date.today())
        goal_plan = Plan(
            title="Goal Plan", plan_type="goal", goal_target_date=date.today()
        )
        async_session.add(daily_plan)
        async_session.add(goal_plan)
        await async_session.commit()

        # Query daily plans
        plan_queries = PlanQueries(async_session)
        daily_plans = await plan_queries.get_plans_by_type("daily")
        goal_plans = await plan_queries.get_plans_by_type("goal")

        assert len(daily_plans) >= 1
        assert len(goal_plans) >= 1
        assert all(p.plan_type == "daily" for p in daily_plans)
        assert all(p.plan_type == "goal" for p in goal_plans)

    async def test_search_plans(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test searching plans by title."""
        # Create a plan
        plan = Plan(
            title="Important Daily Plan",
            description="This is a test plan",
            plan_type="daily",
            plan_date=date.today(),
        )
        async_session.add(plan)
        await async_session.commit()

        # Search for it
        plan_queries = PlanQueries(async_session)
        results = await plan_queries.search_plans("Important")

        assert len(results) > 0
        assert any("Important" in p.title for p in results)


class TestBucketQueries:
    """Test bucket query functions with real database connections."""

    async def test_create_and_get_bucket(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test creating and retrieving a bucket."""
        # Create a plan first
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        # Create a bucket
        bucket = Bucket(
            plan_id=plan.id, name="Morning Tasks", description="Tasks for morning"
        )
        async_session.add(bucket)
        await async_session.commit()
        await async_session.refresh(bucket)

        # Query it
        bucket_queries = BucketQueries(async_session)
        result = await bucket_queries.get_bucket_by_id(bucket.id)

        assert result is not None
        assert result.name == "Morning Tasks"
        assert result.plan_id == plan.id

    async def test_get_buckets_by_plan_id(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test getting buckets for a plan."""
        # Create a plan
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        # Create multiple buckets
        bucket1 = Bucket(plan_id=plan.id, name="Bucket 1", order_index=0)
        bucket2 = Bucket(plan_id=plan.id, name="Bucket 2", order_index=1)
        async_session.add(bucket1)
        async_session.add(bucket2)
        await async_session.commit()

        # Query buckets
        bucket_queries = BucketQueries(async_session)
        buckets = await bucket_queries.get_buckets_by_plan_id(plan.id)

        assert len(buckets) >= 2
        assert all(b.plan_id == plan.id for b in buckets)
        # Should be ordered by index
        assert buckets[0].order_index <= buckets[1].order_index


class TestTaskQueries:
    """Test task query functions with real database connections."""

    async def test_create_and_get_task(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test creating and retrieving a task."""
        # Create plan and bucket
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        bucket = Bucket(plan_id=plan.id, name="Test Bucket")
        async_session.add(bucket)
        await async_session.commit()
        await async_session.refresh(bucket)

        # Create a task
        task = Task(
            bucket_id=bucket.id,
            title="Complete task",
            description="Task description",
            status="pending",
        )
        async_session.add(task)
        await async_session.commit()
        await async_session.refresh(task)

        # Query it
        task_queries = TaskQueries(async_session)
        result = await task_queries.get_task_by_id(task.id)

        assert result is not None
        assert result.title == "Complete task"
        assert result.status == "pending"
        assert result.bucket_id == bucket.id

    async def test_get_tasks_by_bucket_id(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test getting tasks for a bucket."""
        # Create plan and bucket
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        bucket = Bucket(plan_id=plan.id, name="Test Bucket")
        async_session.add(bucket)
        await async_session.commit()
        await async_session.refresh(bucket)

        # Create multiple tasks
        task1 = Task(bucket_id=bucket.id, title="Task 1", order_index=0)
        task2 = Task(bucket_id=bucket.id, title="Task 2", order_index=1)
        async_session.add(task1)
        async_session.add(task2)
        await async_session.commit()

        # Query tasks
        task_queries = TaskQueries(async_session)
        tasks = await task_queries.get_tasks_by_bucket_id(bucket.id)

        assert len(tasks) >= 2
        assert all(t.bucket_id == bucket.id for t in tasks)

    async def test_get_tasks_by_status(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test getting tasks by status."""
        # Create plan and bucket
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        bucket = Bucket(plan_id=plan.id, name="Test Bucket")
        async_session.add(bucket)
        await async_session.commit()
        await async_session.refresh(bucket)

        # Create tasks with different statuses
        pending_task = Task(bucket_id=bucket.id, title="Pending", status="pending")
        completed_task = Task(
            bucket_id=bucket.id, title="Completed", status="completed"
        )
        async_session.add(pending_task)
        async_session.add(completed_task)
        await async_session.commit()

        # Query by status
        task_queries = TaskQueries(async_session)
        pending_tasks = await task_queries.get_tasks_by_status("pending")
        completed_tasks = await task_queries.get_tasks_by_status("completed")

        assert len(pending_tasks) >= 1
        assert len(completed_tasks) >= 1
        assert all(t.status == "pending" for t in pending_tasks)
        assert all(t.status == "completed" for t in completed_tasks)

    async def test_get_subtasks(
        self, async_session: AsyncSession, setup_test_environment
    ):
        """Test getting subtasks (recursive tasks)."""
        # Create plan and bucket
        plan = Plan(title="Test Plan", plan_type="daily", plan_date=date.today())
        async_session.add(plan)
        await async_session.commit()
        await async_session.refresh(plan)

        bucket = Bucket(plan_id=plan.id, name="Test Bucket")
        async_session.add(bucket)
        await async_session.commit()
        await async_session.refresh(bucket)

        # Create parent task
        parent_task = Task(bucket_id=bucket.id, title="Parent Task")
        async_session.add(parent_task)
        await async_session.commit()
        await async_session.refresh(parent_task)

        # Create subtask
        subtask = Task(
            bucket_id=bucket.id,
            title="Subtask",
            parent_task_id=parent_task.id,
        )
        async_session.add(subtask)
        await async_session.commit()

        # Query subtasks
        task_queries = TaskQueries(async_session)
        subtasks = await task_queries.get_subtasks(parent_task.id)

        assert len(subtasks) >= 1
        assert all(t.parent_task_id == parent_task.id for t in subtasks)
