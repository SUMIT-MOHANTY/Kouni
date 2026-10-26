"""
ASGI Entry Point for Production Deployment.

This module serves as the WSGI/ASGI entry point for production servers
like Uvicorn, Gunicorn, or Hypercorn. It exposes the FastAPI application
instance for external ASGI servers to run.

Usage:
    # With Uvicorn directly:
    uvicorn wsgi:app --host 0.0.0.0 --port 8000
    
    # With Gunicorn + Uvicorn workers:
    gunicorn wsgi:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
    
    # With Hypercorn:
    hypercorn wsgi:app --bind 0.0.0.0:8000
"""

from app.main import create_app

# Create the FastAPI application instance
# This is the main entry point for ASGI servers
app = create_app()


# For compatibility with some WSGI-to-ASGI bridges
# This allows the app to be used in hybrid environments
if __name__ == "__main__":
    import uvicorn
    from app.config import get_settings
    
    settings = get_settings()
    
    uvicorn.run(
        "wsgi:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        # Production settings
        reload=False,  # Never reload in production
        workers=1,     # Uvicorn handles workers via process manager
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
