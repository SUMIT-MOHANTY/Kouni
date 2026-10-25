"""
Models Package Initialization

This module exports all SQLAlchemy models for easy importing.
Import models from this package to avoid circular import issues.
"""
from sqlalchemy.orm import relationship

from .user import User
from .user_session import UserSession
from .category import Category
from .task import Task, TaskStatus, TaskPriority
from .task_tag import TaskTag
from .task_history import TaskHistory, HistoryAction


# Attach relationships for all models
# These are attached after all models are defined to avoid circular imports

# User -> UserSession relationship
User.sessions = relationship(
    'UserSession',
    back_populates='user',
    cascade='all, delete-orphan',
    lazy='dynamic'
)

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
