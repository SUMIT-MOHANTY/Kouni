"""
Task Model

SQLAlchemy 2.0 declarative model for tasks with optimistic locking.
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, ForeignKey, DateTime, Integer, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..extensions import db


class TaskStatus(PyEnum):
    """Task status enumeration."""
    ACTIVE = 'active'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'


class TaskPriority(PyEnum):
    """Task priority enumeration."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class Task(db.Model):
    """
    Task model for todo items with optimistic locking.
    
    Tasks are user-owned and can be assigned to categories.
    Supports status tracking, priority levels, due dates, and versioning
    for optimistic locking to prevent concurrent update conflicts.
    
    Attributes:
        id: UUID primary key
        title: Task title
        description: Task description (optional)
        status: Task status (active/completed/archived)
        priority: Task priority (low/medium/high)
        due_date: Task due date (optional)
        version: Optimistic locking version number
        user_id: Foreign key to users table (owner)
        created_at: Task creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = 'tasks'
    
    # Primary key - UUID for security and scalability
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    
    # Task content
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    # Task status with enum
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name='task_status'),
        default=TaskStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    # Task priority with enum
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name='task_priority'),
        default=TaskPriority.MEDIUM,
        nullable=False,
        index=True
    )
    
    # Due date for the task
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True
    )
    
    # Optimistic locking version field
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False
    )
    
    # Foreign key to users table with cascade delete
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationship to User model
    user: Mapped['User'] = relationship('User', back_populates='tasks')
    
    # Relationship to TaskTag (junction table for categories)
    task_tags: Mapped[list['TaskTag']] = relationship(
        'TaskTag',
        back_populates='task',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # Relationship to TaskHistory (audit log)
    history: Mapped[list['TaskHistory']] = relationship(
        'TaskHistory',
        back_populates='task',
        cascade='all, delete-orphan',
        lazy='dynamic',
        order_by='desc(TaskHistory.timestamp)'
    )
    
    def increment_version(self) -> None:
        """Increment the version number for optimistic locking."""
        self.version += 1
    
    def is_overdue(self) -> bool:
        """
        Check if the task is overdue.
        
        Returns:
            bool: True if task is overdue, False otherwise
        """
        if self.due_date is None:
            return False
        return datetime.utcnow() > self.due_date and self.status != TaskStatus.COMPLETED
    
    def complete(self) -> None:
        """Mark the task as completed."""
        self.status = TaskStatus.COMPLETED
        self.increment_version()
    
    def uncomplete(self) -> None:
        """Mark the task as active (uncomplete)."""
        self.status = TaskStatus.ACTIVE
        self.increment_version()
    
    def archive(self) -> None:
        """Archive the task."""
        self.status = TaskStatus.ARCHIVED
        self.increment_version()
    
    def to_dict(self, include_user: bool = False, include_categories: bool = False) -> dict:
        """
        Convert task to dictionary representation.
        
        Args:
            include_user: Whether to include user data
            include_categories: Whether to include category data
            
        Returns:
            dict: Task data dictionary
        """
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'version': self.version,
            'is_overdue': self.is_overdue(),
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_user and self.user:
            data['user'] = self.user.to_dict()
        
        if include_categories:
            data['categories'] = [
                tag.category.to_dict() for tag in self.task_tags
                if tag.category
            ]
        
        return data
    
    def __repr__(self) -> str:
        """String representation of Task."""
        return f"<Task(id={self.id}, title={self.title}, status={self.status}, priority={self.priority})>"
