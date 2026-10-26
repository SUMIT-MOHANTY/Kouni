"""
FastAPI Application Factory for LMS Backend.

This module creates and configures the FastAPI application with:
- CORS middleware for frontend communication
- Health check endpoint with database connectivity verification
- API router registration structure for extensibility
- Automatic OpenAPI contract export on startup
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings, Settings
from app.extensions import check_db_connection, close_db, init_db


def create_app() -> FastAPI:
    """
    Application factory for creating FastAPI instances.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    settings = get_settings()
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Application lifespan context manager.
        
        Handles startup and shutdown events:
        - Startup: Initialize database, export OpenAPI contract
        - Shutdown: Close database connections
        """
        # Startup: Initialize database tables (for development)
        if settings.is_development:
            await init_db()
        
        # Export OpenAPI contract for frontend consumption
        await export_openapi_contract(app)
        
        yield
        
        # Shutdown: Close database connections
        await close_db()
    
    # Create FastAPI application
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Learning Management System Backend API",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )
    
    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods_list,
        allow_headers=settings.cors_allow_headers_list,
    )
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """
        Health check endpoint with database connectivity verification.
        
        Returns:
            dict: Health status with database connection state
        """
        db_healthy = await check_db_connection()
        
        if not db_healthy:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "status": "error",
                    "database": "disconnected",
                    "message": "Database connection failed"
                }
            )
        
        return {
            "status": "ok",
            "database": "connected",
            "version": settings.app_version,
            "environment": settings.environment,
        }
    
    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """
        Root endpoint with API information.
        
        Returns:
            dict: Basic API information
        """
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "docs_url": "/docs" if not settings.is_production else None,
        }
    
    # API version prefix for all routes
    api_v1_prefix = "/api/v1"
    
    # Placeholder for future API routers
    # from app.api.v1 import users, courses, enrollments, assessments, certificates, discussions
    # app.include_router(users.router, prefix=api_v1_prefix, tags=["Users"])
    # app.include_router(courses.router, prefix=api_v1_prefix, tags=["Courses"])
    # app.include_router(enrollments.router, prefix=api_v1_prefix, tags=["Enrollments"])
    # app.include_router(assessments.router, prefix=api_v1_prefix, tags=["Assessments"])
    # app.include_router(certificates.router, prefix=api_v1_prefix, tags=["Certificates"])
    # app.include_router(discussions.router, prefix=api_v1_prefix, tags=["Discussions"])
    
    return app


async def export_openapi_contract(app: FastAPI) -> None:
    """
    Export OpenAPI schema to JSON file for frontend consumption.
    
    This generates the API contract that frontend developers can use
    to understand available endpoints and request/response schemas.
    
    Args:
        app: FastAPI application instance
    """
    settings = get_settings()
    
    # Create contracts directory if it doesn't exist
    contracts_dir = Path("/workspace/backend/.agent/contracts")
    contracts_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate OpenAPI schema
    openapi_schema = app.openapi()
    
    # Add metadata
    openapi_schema["info"]["x-environment"] = settings.environment
    openapi_schema["info"]["x-generated-at"] = str(os.path.getmtime(__file__))
    
    # Write to file
    contract_path = contracts_dir / "api_contract.json"
    with open(contract_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    
    print(f"✅ API contract exported to: {contract_path}")


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
