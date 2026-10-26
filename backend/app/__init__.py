"""
LMS Backend Application Package.

This package contains the FastAPI backend for the Learning Management System.

Modules:
    config: Pydantic settings and configuration
    extensions: SQLAlchemy database extensions
    main: FastAPI application factory
    seeds: Database seeding infrastructure

Usage:
    # Run development server
    python -m app
    
    # Run with custom settings
    python -m app --host 0.0.0.0 --port 8080
"""

__version__ = "1.0.0"
__author__ = "LMS Team"

from app.config import get_settings, settings
from app.extensions import Base, get_db, engine, AsyncSessionLocal

__all__ = [
    "get_settings",
    "settings",
    "Base",
    "get_db",
    "engine",
    "AsyncSessionLocal",
]
