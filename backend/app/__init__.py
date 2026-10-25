"""
Flask Application Factory

This module implements the Flask application factory pattern, enabling
creation of Flask app instances with proper configuration and extension
initialization.
"""
import os
from datetime import datetime
from flask import Flask, jsonify
from .config import get_config
from .extensions import init_extensions, db


def create_app(config_name=None):
    """
    Flask application factory.
    
    Creates and configures a Flask application instance with the specified
    configuration, initializes extensions, and registers blueprints.
    
    Args:
        config_name: Configuration name ('development', 'testing', 'production')
                    If None, uses FLASK_ENV environment variable.
    
    Returns:
        Flask: Configured Flask application instance
    """
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    if config_name:
        os.environ['FLASK_ENV'] = config_name
    
    config = get_config()
    app.config.from_object(config)
    
    # Initialize extensions
    init_extensions(app)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Register error handlers
    _register_error_handlers(app)
    
    # Register healthcheck endpoint
    _register_healthcheck(app)
    
    # Shell context
    @app.shell_context_processor
    def shell_context():
        """Add database and models to shell context."""
        return {
            'db': db,
            'app': app
        }
    
    return app


def _register_blueprints(app):
    """
    Register Flask blueprints.
    
    Blueprints are registered here to avoid circular imports.
    Domain blueprints will be added as they are implemented.
    
    Args:
        app: Flask application instance
    """
    # Blueprints will be registered here as they are created:
    # - auth_bp: Authentication endpoints (/api/auth)
    # - users_bp: User management endpoints (/api/users)
    # - tasks_bp: Task management endpoints (/api/tasks)
    # - categories_bp: Category management endpoints (/api/categories)
    # - admin_bp: Admin operations endpoints (/api/admin)
    
    # Placeholder for future blueprint registrations
    # from .routes.auth import auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/api/auth')
    
    pass


def _register_error_handlers(app):
    """
    Register global error handlers.
    
    Args:
        app: Flask application instance
    """
    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request errors."""
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized errors."""
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': 'Authentication required'
        }), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden errors."""
        return jsonify({
            'success': False,
            'error': 'Forbidden',
            'message': 'Access denied'
        }), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found errors."""
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': 'Resource not found'
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed errors."""
        return jsonify({
            'success': False,
            'error': 'Method Not Allowed',
            'message': 'HTTP method not allowed for this endpoint'
        }), 405
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        """Handle 422 Unprocessable Entity errors."""
        return jsonify({
            'success': False,
            'error': 'Unprocessable Entity',
            'message': str(error.description) if hasattr(error, 'description') else 'Validation failed'
        }), 422
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handle 500 Internal Server Error."""
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


def _register_healthcheck(app):
    """
    Register the healthcheck endpoint.
    
    Args:
        app: Flask application instance
    """
    @app.route('/api/health', methods=['GET'])
    def healthcheck():
        """
        Healthcheck endpoint.
        
        Returns the current health status of the application including:
        - Application status
        - Database connectivity status
        - Current timestamp
        - Environment information
        
        Returns:
            JSON response with health status
        """
        health_status = {
            'success': True,
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'environment': os.environ.get('FLASK_ENV', 'development'),
            'version': '1.0.0'
        }
        
        # Check database connectivity
        try:
            # Attempt a simple database query
            from sqlalchemy import text
            with db.engine.connect() as connection:
                connection.execute(text('SELECT 1'))
                connection.commit()
            health_status['database'] = 'connected'
        except Exception as e:
            health_status['database'] = 'disconnected'
            health_status['database_error'] = str(e)
            health_status['status'] = 'degraded'
        
        # Determine HTTP status code based on health
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return jsonify(health_status), status_code


def init_db():
    """
    Initialize the database by creating all tables.
    
    This is useful for initial setup and testing.
    """
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database tables created successfully.")


# Application entry point for development
if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)
