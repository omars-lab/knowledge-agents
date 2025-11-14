"""
Database queries for plan operations.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.plan import Plan


class PlanQueries:
    """Database queries for plans."""

    def __init__(self, database_session: AsyncSession):
        self.database_session = database_session

    async def get_all_plans(self, include_buckets: bool = False) -> List[Plan]:
        """Get all plans.

        Args:
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of all plans
        """
        query = select(Plan)
        if include_buckets:
            query = query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_plan_by_id(
        self, plan_id: int, include_buckets: bool = False
    ) -> Optional[Plan]:
        """Get plan by ID.

        Args:
            plan_id: The plan ID
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            Plan if found, None otherwise
        """
        query = select(Plan).where(Plan.id == plan_id)
        if include_buckets:
            query = query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(query)
        return result.scalar_one_or_none()

    async def get_plans_by_type(
        self, plan_type: str, include_buckets: bool = False
    ) -> List[Plan]:
        """Get plans by type (daily or goal).

        Args:
            plan_type: Either 'daily' or 'goal'
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of plans matching the type
        """
        query = select(Plan).where(Plan.plan_type == plan_type)
        if include_buckets:
            query = query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def get_plan_by_date(
        self, plan_date: date, include_buckets: bool = False
    ) -> Optional[Plan]:
        """Get daily plan by date.

        Args:
            plan_date: The date to search for
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            Plan if found, None otherwise
        """
        query = select(Plan).where(
            Plan.plan_type == "daily", Plan.plan_date == plan_date
        )
        if include_buckets:
            query = query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(query)
        return result.scalar_one_or_none()

    async def get_plans_by_date_range(
        self, start_date: date, end_date: date, include_buckets: bool = False
    ) -> List[Plan]:
        """Get daily plans within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of plans within the date range
        """
        query = select(Plan).where(
            Plan.plan_type == "daily",
            Plan.plan_date >= start_date,
            Plan.plan_date <= end_date,
        )
        if include_buckets:
            query = query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(query)
        return result.scalars().all()

    async def search_plans(
        self, query: str, include_buckets: bool = False
    ) -> List[Plan]:
        """Search plans by title or description.

        Args:
            query: Search term
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of plans matching the search term
        """
        search_query = select(Plan).where(
            or_(Plan.title.ilike(f"%{query}%"), Plan.description.ilike(f"%{query}%"))
        )
        if include_buckets:
            search_query = search_query.options(selectinload(Plan.buckets))
        result = await self.database_session.execute(search_query)
        return result.scalars().all()

    async def get_goal_plans(self, include_buckets: bool = False) -> List[Plan]:
        """Get all goal-focused plans.

        Args:
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of goal-focused plans
        """
        return await self.get_plans_by_type("goal", include_buckets=include_buckets)

    async def get_daily_plans(self, include_buckets: bool = False) -> List[Plan]:
        """Get all daily plans.

        Args:
            include_buckets: If True, eagerly load buckets relationship

        Returns:
            List of daily plans
        """
        return await self.get_plans_by_type("daily", include_buckets=include_buckets)
