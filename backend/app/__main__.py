"""
Backend Application Entry Point

This module serves as the Python entrypoint for running the backend application.
It allows the application to be started using:
    python -m backend.app
    
Or imported as a module for ASGI servers like uvicorn:
    uvicorn backend.app:app --reload
"""
import os
import sys

# Add the backend directory to the path for proper imports
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app

# Create the Flask application instance
# This 'app' variable is exposed for ASGI/WSGI servers
config_name = os.environ.get('FLASK_ENV', 'development')
app = create_app(config_name)


def main():
    """
    Main entry point for running the application directly.
    
    This function is called when the module is run as:
        python -m backend.app
    """
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', '5000'))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"Starting Flask application on {host}:{port}")
    print(f"Environment: {config_name}")
    print(f"Debug mode: {debug}")
    
    app.run(
        host=host,
        port=port,
        debug=debug
    )


if __name__ == '__main__':
    main()
