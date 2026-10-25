"""
Models Package Initialization

This module exports all SQLAlchemy models for easy importing.
Import models from this package to avoid circular import issues.
"""
from .user import User
from .user_session import UserSession
from .category import Category
from .task import Task, TaskStatus, TaskPriority
from .task_tag import TaskTag
from .task_history import TaskHistory, HistoryAction

# Attach the sessions relationship to User model after both are defined
# This avoids circular import issues between User and UserSession
UserSession._attach_user_relationship()

# Attach relationships for task domain models
# These are attached after all models are defined to avoid circular imports
def _attach_task_relationships():
    """Attach relationships for task domain models."""
    from .user import User
    
    # User -> Categories relationship
    User.categories = relationship(
        'Category',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # User -> Tasks relationship
    User.tasks = relationship(
        'Task',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )
    
    # User -> TaskHistory relationship (audit trail)
    User.task_history = relationship(
        'TaskHistory',
        back_populates='user',
        lazy='dynamic'
    )

# Import relationship to attach user relationships
from sqlalchemy.orm import relationship

# Attach all relationships
_attach_task_relationships()

__all__ = [
    'User',
    'UserSession',
    'Category',
    'Task',
    'TaskStatus',
    'TaskPriority',
    'TaskTag',
    'TaskHistory',
    'HistoryAction',
]
