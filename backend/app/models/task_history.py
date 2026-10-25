"""
Task History Model

SQLAlchemy 2.0 declarative model for task audit logging.
Tracks all task mutations with field changes for audit purposes.
"""
import uuid
import json
from datetime import datetime
from typing import Any
from sqlalchemy import String, ForeignKey, DateTime, Text, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..extensions import db


class TaskHistory(db.Model):
    """
    Task history model for audit logging of task changes.
    
    Tracks all mutations to tasks including field changes, who made the change,
    and when the change occurred. Supports JSON field_changes for flexible
    tracking of any field modifications.
    
    Attributes:
        id: UUID primary key
        task_id: Foreign key to tasks table
        action: Action performed (create, update, delete, complete, uncomplete, archive)
        field_changes: JSON string of field changes {field: {old: value, new: value}}
        user_id: Foreign key to users table (who made the change)
        timestamp: When the change occurred
    """
    
    __tablename__ = 'task_history'
    
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
    
    # Action performed on the task
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    # JSON field changes - stores {field_name: {'old': old_value, 'new': new_value}}
    field_changes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    
    # Foreign key to users table (who made the change)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    
    # Timestamp when the change occurred
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Relationship to Task model
    task: Mapped['Task'] = relationship('Task', back_populates='history')
    
    # Relationship to User model (who made the change)
    user: Mapped['User | None'] = relationship('User', back_populates='task_history')
    
    def set_field_changes(self, changes: dict[str, dict[str, Any]]) -> None:
        """
        Set field changes as JSON string.
        
        Args:
            changes: Dictionary of field changes in format:
                    {field_name: {'old': old_value, 'new': new_value}}
        """
        self.field_changes = json.dumps(changes, default=str)
    
    def get_field_changes(self) -> dict[str, dict[str, Any]]:
        """
        Get field changes as dictionary.
        
        Returns:
            dict: Field changes dictionary
        """
        if self.field_changes:
            return json.loads(self.field_changes)
        return {}
    
    def to_dict(self, include_task: bool = False, include_user: bool = False) -> dict:
        """
        Convert task history to dictionary representation.
        
        Args:
            include_task: Whether to include task data
            include_user: Whether to include user data
            
        Returns:
            dict: TaskHistory data dictionary
        """
        data = {
            'id': self.id,
            'task_id': self.task_id,
            'action': self.action,
            'field_changes': self.get_field_changes(),
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
        
        if include_task and self.task:
            data['task'] = self.task.to_dict()
        
        if include_user and self.user:
            data['user'] = self.user.to_dict()
            
        return data
    
    def __repr__(self) -> str:
        """String representation of TaskHistory."""
        return f"<TaskHistory(id={self.id}, task_id={self.task_id}, action={self.action}, timestamp={self.timestamp})>"


# Action constants for task history
class HistoryAction:
    """Constants for task history actions."""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    COMPLETE = 'complete'
    UNCOMPLETE = 'uncomplete'
    ARCHIVE = 'archive'
    RESTORE = 'restore'
    ADD_CATEGORY = 'add_category'
    REMOVE_CATEGORY = 'remove_category'
