"""
Task model for database operations.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import Base


class Task(Base):
    """Task model for storing task information (recursive - can have subtasks)."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    bucket_id = Column(
        Integer, ForeignKey("buckets.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parent_task_id = Column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )  # For recursive subtasks
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="pending", nullable=False)
    priority = Column(
        Integer, default=0, nullable=False
    )  # 0 = normal, higher = more priority
    order_index = Column(Integer, default=0, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default="CURRENT_TIMESTAMP", nullable=False
    )

    # Relationships
    bucket = relationship("Bucket", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id], backref="subtasks")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="check_task_status",
        ),
    )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "bucket_id": self.bucket_id,
            "parent_task_id": self.parent_task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "order_index": self.order_index,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
