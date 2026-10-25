"""
Pytest Configuration and Fixtures

This module provides pytest fixtures and configuration for testing the Flask application.
"""
import pytest
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.app.extensions import db


@pytest.fixture
def app():
    """Create and configure a test Flask application."""
    app = create_app('testing')
    
    # Create an application context
    with app.app_context():
        # Create all tables
        db.create_all()
        yield app
        # Clean up
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner for the app."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Provide a database session for tests."""
    with app.app_context():
        yield db.session
        # Rollback after each test
        db.session.rollback()
