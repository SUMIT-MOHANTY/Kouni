"""
Flask Application Configuration

Environment-based configuration supporting SQLite (development) and PostgreSQL (production).
"""
import os
from datetime import timedelta


class Config:
    """Base configuration class with common settings."""
    
    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-dev-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', 15)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_EXPIRES_DAYS', 7)))
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:4200,http://localhost:3000').split(',')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # Database settings - SQLAlchemy 2.0
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = os.environ.get('SQLALCHEMY_ECHO', 'false').lower() == 'true'
    
    # Pagination defaults
    DEFAULT_PER_PAGE = int(os.environ.get('DEFAULT_PER_PAGE', 20))
    MAX_PER_PAGE = int(os.environ.get('MAX_PER_PAGE', 100))
    
    # Security settings
    BCRYPT_LOG_ROUNDS = int(os.environ.get('BCRYPT_LOG_ROUNDS', 12))
    
    @staticmethod
    def init_app(app):
        """Initialize application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Development configuration with SQLite database."""
    
    DEBUG = True
    TESTING = False
    
    # SQLite database for development
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'sqlite:///dev_todo_app.db'
    )


class TestingConfig(Config):
    """Testing configuration with in-memory SQLite."""
    
    DEBUG = False
    TESTING = True
    
    # In-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TEST_DATABASE_URL',
        'sqlite:///:memory:'
    )
    
    # Faster bcrypt for tests
    BCRYPT_LOG_ROUNDS = 4


class ProductionConfig(Config):
    """Production configuration with PostgreSQL database."""
    
    DEBUG = False
    TESTING = False
    
    # PostgreSQL database for production (via DATABASE_URL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError(
            "DATABASE_URL environment variable must be set in production"
        )
    
    # Production security settings
    SECRET_KEY = os.environ.get('SECRET_KEY')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    
    if not SECRET_KEY or not JWT_SECRET_KEY:
        raise ValueError(
            "SECRET_KEY and JWT_SECRET_KEY must be set in production"
        )
    
    @classmethod
    def init_app(cls, app):
        """Initialize production application with logging."""
        Config.init_app(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


# Configuration mapping
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get the appropriate configuration based on environment."""
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
