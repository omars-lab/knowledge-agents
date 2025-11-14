"""
Database queries for task operations.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.bucket import Bucket
from ..models.task import Task


class TaskQueries:
    """Database queries for tasks."""

    def __init__(self, database_session: AsyncSession):
        self.database_session = database_session

    async def get_all_tasks(self, include_subtasks: bool = False) -> List[Task]:
        """Get all tasks.

        Args:
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of all tasks
        """
        query = select(Task)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_task_by_id(
        self, task_id: int, include_subtasks: bool = False
    ) -> Optional[Task]:
        """Get task by ID.

        Args:
            task_id: The task ID
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            Task if found, None otherwise
        """
        query = select(Task).where(Task.id == task_id)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalar_one_or_none()

    async def get_tasks_by_bucket_id(
        self,
        bucket_id: int,
        include_subtasks: bool = False,
        order_by_index: bool = True,
    ) -> List[Task]:
        """Get all tasks for a specific bucket.

        Args:
            bucket_id: The bucket ID
            include_subtasks: If True, eagerly load subtasks relationship
            order_by_index: If True, order tasks by order_index

        Returns:
            List of tasks for the bucket
        """
        query = select(Task).where(Task.bucket_id == bucket_id)
        if order_by_index:
            query = query.order_by(Task.order_index)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_tasks_by_plan_id(
        self, plan_id: int, include_subtasks: bool = False
    ) -> List[Task]:
        """Get all tasks for a specific plan (through buckets).

        Args:
            plan_id: The plan ID
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks for the plan
        """
        query = select(Task).join(Bucket).where(Bucket.plan_id == plan_id)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_tasks_by_status(
        self, status: str, include_subtasks: bool = False
    ) -> List[Task]:
        """Get tasks by status.

        Args:
            status: Task status (pending, in_progress, completed, cancelled)
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks with the specified status
        """
        query = select(Task).where(Task.status == status)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_subtasks(self, parent_task_id: int) -> List[Task]:
        """Get all subtasks for a parent task.

        Args:
            parent_task_id: The parent task ID

        Returns:
            List of subtasks
        """
        query = select(Task).where(Task.parent_task_id == parent_task_id)
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_tasks_without_bucket(
        self, include_subtasks: bool = False
    ) -> List[Task]:
        """Get tasks that are not associated with any bucket (plan root tasks).

        Args:
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks without a bucket
        """
        query = select(Task).where(Task.bucket_id.is_(None))
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_tasks_by_priority(
        self, min_priority: int = 0, include_subtasks: bool = False
    ) -> List[Task]:
        """Get tasks with priority >= min_priority.

        Args:
            min_priority: Minimum priority level (0 = normal, higher = more priority)
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks meeting the priority threshold
        """
        query = select(Task).where(Task.priority >= min_priority)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_tasks_due_before(
        self, due_date: datetime, include_subtasks: bool = False
    ) -> List[Task]:
        """Get tasks due before a specific date.

        Args:
            due_date: The cutoff date
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks due before the specified date
        """
        query = select(Task).where(Task.due_date.isnot(None), Task.due_date <= due_date)
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_completed_tasks(self, include_subtasks: bool = False) -> List[Task]:
        """Get all completed tasks.

        Args:
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of completed tasks
        """
        return await self.get_tasks_by_status(
            "completed", include_subtasks=include_subtasks
        )

    async def get_pending_tasks(self, include_subtasks: bool = False) -> List[Task]:
        """Get all pending tasks.

        Args:
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of pending tasks
        """
        return await self.get_tasks_by_status(
            "pending", include_subtasks=include_subtasks
        )

    async def search_tasks(
        self, query: str, include_subtasks: bool = False
    ) -> List[Task]:
        """Search tasks by title or description.

        Args:
            query: Search term
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks matching the search term
        """
        search_query = select(Task).where(
            or_(Task.title.ilike(f"%{query}%"), Task.description.ilike(f"%{query}%"))
        )
        if include_subtasks:
            search_query = search_query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(search_query)
        return result.scalars().all()

    async def get_tasks_by_date_range(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_subtasks: bool = False,
    ) -> List[Task]:
        """Get tasks created within a date range.

        Args:
            start_date: Start date (inclusive), None for no lower bound
            end_date: End date (inclusive), None for no upper bound
            include_subtasks: If True, eagerly load subtasks relationship

        Returns:
            List of tasks created within the date range
        """
        conditions = []
        if start_date:
            conditions.append(Task.created_at >= start_date)
        if end_date:
            conditions.append(Task.created_at <= end_date)

        query = select(Task)
        if conditions:
            query = query.where(and_(*conditions))
        if include_subtasks:
            query = query.options(selectinload(Task.subtasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()
