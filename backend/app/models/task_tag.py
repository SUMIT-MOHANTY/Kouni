"""
TaskTag Model

SQLAlchemy 2.0 declarative model for many-to-many relationship
between tasks and categories.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..extensions import db


class TaskTag(db.Model):
    """
    TaskTag junction model for many-to-many relationship between tasks and categories.
    
    This model allows tasks to have multiple categories and categories to have multiple tasks.
    Each task-category pair is unique.
    
    Attributes:
        id: UUID primary key
        task_id: Foreign key to tasks table
        category_id: Foreign key to categories table
        created_at: Association creation timestamp
    """
    
    __tablename__ = 'task_tags'
    
    # Primary key - UUID for security and scalability
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Foreign key to tasks table with cascade delete
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('tasks.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Foreign key to categories table with cascade delete
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('categories.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationship to Task model
    task: Mapped['Task'] = relationship('Task', back_populates='task_tags')
    
    # Relationship to Category model
    category: Mapped['Category'] = relationship('Category', back_populates='task_tags')
    
    # Unique constraint to prevent duplicate task-category associations
    __table_args__ = (
        UniqueConstraint('task_id', 'category_id', name='uq_task_category'),
    )
    
    def to_dict(self, include_task: bool = False, include_category: bool = False) -> dict:
        """
        Convert task tag to dictionary representation.
        
        Args:
            include_task: Whether to include task data
            include_category: Whether to include category data
            
        Returns:
            dict: TaskTag data dictionary
        """
        data = {
            'id': self.id,
            'task_id': self.task_id,
            'category_id': self.category_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_task and self.task:
            data['task'] = self.task.to_dict()
        
        if include_category and self.category:
            data['category'] = self.category.to_dict()
            
        return data
    
    def __repr__(self) -> str:
        """String representation of TaskTag."""
        return f"<TaskTag(id={self.id}, task_id={self.task_id}, category_id={self.category_id})>"
