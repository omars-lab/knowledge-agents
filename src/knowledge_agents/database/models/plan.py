"""
Plan model for database operations.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Column, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class Plan(Base):
    """Plan model for storing plan information (daily or goal-focused)."""

    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    plan_type = Column(String(50), nullable=False)  # 'daily' or 'goal'
    plan_date = Column(Date, nullable=True)  # For daily plans
    goal_target_date = Column(Date, nullable=True)  # For goal-focused plans
    created_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )

    # Relationships
    buckets = relationship(
        "Bucket", back_populates="plan", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("plan_type IN ('daily', 'goal')", name="check_plan_type"),
    )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "plan_type": self.plan_type,
            "plan_date": self.plan_date.isoformat() if self.plan_date else None,
            "goal_target_date": self.goal_target_date.isoformat()
            if self.goal_target_date
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
