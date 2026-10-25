"""
WSGI/ASGI Entry Point

This module provides the entry point for production deployment
using Gunicorn, uvicorn, or other WSGI/ASGI servers.

Usage:
    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
    uvicorn wsgi:app --host 0.0.0.0 --port 5000

Environment Variables:
    FLASK_ENV: Application environment (development, testing, production)
    DATABASE_URL: Database connection URL (required for production)
    SECRET_KEY: Flask secret key (required for production)
    JWT_SECRET_KEY: JWT signing secret (required for production)
"""
import os
import sys

# Add the backend directory to the path so 'app' can be imported
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app

# Get configuration from environment
config_name = os.environ.get('FLASK_ENV', 'development')

# Create the Flask application instance
flask_app = create_app(config_name)

# Wrap Flask app with ASGI middleware for uvicorn compatibility
try:
    from asgiref.wsgi import WsgiToAsgi
    app = WsgiToAsgi(flask_app)
except ImportError:
    # Fallback: if asgiref is not available, just expose the Flask app
    # Note: This won't work with uvicorn directly, but allows import
    app = flask_app

# For Gunicorn and other WSGI servers
# The 'app' variable is the WSGI/ASGI callable

if __name__ == "__main__":
    # Development server entry point
    # In production, use Gunicorn or uvicorn instead
    flask_app.run(
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=int(os.environ.get('FLASK_PORT', 5000)),
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    )
