"""
Flask Extensions Singletons

This module initializes Flask extensions as singletons to avoid circular imports
and enable the application factory pattern.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_cors import CORS
from flask_restx import Api


# SQLAlchemy 2.0 ORM instance
db = SQLAlchemy()

# Alembic migration manager
migrate = Migrate()

# Flask-Login session manager
login_manager = LoginManager()

# CORS extension for cross-origin requests
cors = CORS()

# Flask-RESTX API instance
api = Api(
    version='1.0',
    title='Todo Application API',
    description='RESTful API for the Todo Application',
    doc='/api/docs',
    prefix='/api'
)


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
    
    # Initialize Flask-RESTX API with app
    api.init_app(app)
    
    # Register API namespaces
    _register_namespaces()


def _register_namespaces():
    """
    Register Flask-RESTX namespaces with the API instance.
    
    Namespaces are registered here to avoid circular imports.
    """
    # Import and register auth namespace
    from .api.auth import auth_ns
    api.add_namespace(auth_ns, path='/auth')
    
    # Import and register tasks namespace
    from .api.tasks import tasks_ns
    api.add_namespace(tasks_ns, path='/tasks')
    
    # Import and register categories namespace
    from .api.categories import categories_ns
    api.add_namespace(categories_ns, path='/categories')


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


def get_api():
    """
    Get the Flask-RESTX API instance.
    
    Returns:
        Api: The RESTX API extension instance
    """
    return api
