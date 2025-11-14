"""
Bucket model for database operations.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .base import Base


class Bucket(Base):
    """Bucket model for storing bucket information (sets of tasks within a plan)."""

    __tablename__ = "buckets"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(
        Integer, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )

    # Relationships
    plan = relationship("Plan", back_populates="buckets")
    tasks = relationship("Task", back_populates="bucket", cascade="all, delete-orphan")

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "name": self.name,
            "description": self.description,
            "order_index": self.order_index,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
