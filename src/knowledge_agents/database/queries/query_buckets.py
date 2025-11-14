"""
Database queries for bucket operations.
"""
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.bucket import Bucket


class BucketQueries:
    """Database queries for buckets."""

    def __init__(self, database_session: AsyncSession):
        self.database_session = database_session

    async def get_all_buckets(self, include_tasks: bool = False) -> List[Bucket]:
        """Get all buckets.

        Args:
            include_tasks: If True, eagerly load tasks relationship

        Returns:
            List of all buckets
        """
        query = select(Bucket)
        if include_tasks:
            query = query.options(selectinload(Bucket.tasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_bucket_by_id(
        self, bucket_id: int, include_tasks: bool = False
    ) -> Optional[Bucket]:
        """Get bucket by ID.

        Args:
            bucket_id: The bucket ID
            include_tasks: If True, eagerly load tasks relationship

        Returns:
            Bucket if found, None otherwise
        """
        query = select(Bucket).where(Bucket.id == bucket_id)
        if include_tasks:
            query = query.options(selectinload(Bucket.tasks))
        result = await self.database_session.execute(query)
        return result.scalar_one_or_none()

    async def get_buckets_by_plan_id(
        self, plan_id: int, include_tasks: bool = False, order_by_index: bool = True
    ) -> List[Bucket]:
        """Get all buckets for a specific plan.

        Args:
            plan_id: The plan ID
            include_tasks: If True, eagerly load tasks relationship
            order_by_index: If True, order buckets by order_index

        Returns:
            List of buckets for the plan
        """
        query = select(Bucket).where(Bucket.plan_id == plan_id)
        if order_by_index:
            query = query.order_by(Bucket.order_index)
        if include_tasks:
            query = query.options(selectinload(Bucket.tasks))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def search_buckets(
        self, query: str, include_tasks: bool = False
    ) -> List[Bucket]:
        """Search buckets by name or description.

        Args:
            query: Search term
            include_tasks: If True, eagerly load tasks relationship

        Returns:
            List of buckets matching the search term
        """
        search_query = select(Bucket).where(
            or_(Bucket.name.ilike(f"%{query}%"), Bucket.description.ilike(f"%{query}%"))
        )
        if include_tasks:
            search_query = search_query.options(selectinload(Bucket.tasks))
        result = await self.database_session.execute(search_query)
        return result.scalars().all()

    async def get_bucket_by_name_and_plan(
        self, name: str, plan_id: int, include_tasks: bool = False
    ) -> Optional[Bucket]:
        """Get bucket by name within a specific plan.

        Args:
            name: The bucket name
            plan_id: The plan ID
            include_tasks: If True, eagerly load tasks relationship

        Returns:
            Bucket if found, None otherwise
        """
        query = select(Bucket).where(
            Bucket.name.ilike(f"%{name}%"), Bucket.plan_id == plan_id
        )
        if include_tasks:
            query = query.options(selectinload(Bucket.tasks))
        result = await self.database_session.execute(query)
        return result.scalar_one_or_none()
