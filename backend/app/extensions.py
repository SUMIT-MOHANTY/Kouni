"""
Flask Extensions Singletons

This module initializes Flask extensions as singletons to avoid circular imports
and enable the application factory pattern.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS


# SQLAlchemy 2.0 ORM instance
db = SQLAlchemy()

# Alembic migration manager
migrate = Migrate()

# Flask-Login session manager
login_manager = LoginManager()

# CORS extension for cross-origin requests
cors = CORS()


def init_extensions(app):
    """
    Initialize all Flask extensions with the application instance.
    
    Args:
        app: Flask application instance
    """
    # Initialize SQLAlchemy with app
    db.init_app(app)
    
    # Initialize Migrate with app and db
    migrate.init_app(app, db)
    
    # Initialize LoginManager with app
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Initialize CORS with app
    cors.init_app(
        app,
        origins=app.config.get('CORS_ORIGINS', ['http://localhost:4200']),
        supports_credentials=app.config.get('CORS_SUPPORTS_CREDENTIALS', True),
        allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
        methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
    )


def get_db():
    """
    Get the SQLAlchemy database instance.
    
    Returns:
        SQLAlchemy: The database extension instance
    """
    return db


def get_migrate():
    """
    Get the Flask-Migrate instance.
    
    Returns:
        Migrate: The migration extension instance
    """
    return migrate


def get_login_manager():
    """
    Get the Flask-Login manager instance.
    
    Returns:
        LoginManager: The login manager extension instance
    """
    return login_manager


def get_cors():
    """
    Get the Flask-CORS instance.
    
    Returns:
        CORS: The CORS extension instance
    """
    return cors
