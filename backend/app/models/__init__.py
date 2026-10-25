"""
Models Package Initialization

This module exports all SQLAlchemy models for easy importing.
Import models from this package to avoid circular import issues.
"""
from .user import User
from .user_session import UserSession

# Attach the sessions relationship to User model after both are defined
# This avoids circular import issues between User and UserSession
UserSession._attach_user_relationship()

__all__ = [
    'User',
    'UserSession',
]
