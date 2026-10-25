"""
Main Application Entry Point for ASGI Servers

This module provides the ASGI-compatible entry point for running the backend
application with uvicorn or other ASGI servers.

Usage:
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 5000
    
Or using Python module syntax:
    python -m uvicorn backend.app.main:app --reload
"""
import os
import sys

# Add the backend directory to the path for proper imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app

# Create the Flask application instance
config_name = os.environ.get('FLASK_ENV', 'development')
flask_app = create_app(config_name)

# Wrap Flask app with ASGI middleware for uvicorn compatibility
try:
    from asgiref.wsgi import WsgiToAsgi
    app = WsgiToAsgi(flask_app)
except ImportError:
    # Fallback: if asgiref is not available, just expose the Flask app
    # Note: This won't work with uvicorn directly, but allows import
    app = flask_app


def main():
    """
    Main entry point for running the application.
    
    This function can be called when running the module directly.
    """
    import uvicorn
    
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    reload = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"Starting ASGI server on {host}:{port}")
    print(f"Environment: {config_name}")
    print(f"Reload: {reload}")
    
    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == '__main__':
    main()
