"""
Pydantic Settings for LMS Backend Application.

This module defines environment-based configuration using Pydantic v2 Settings.
All sensitive values are loaded from environment variables with sensible defaults
for development.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, computed_field


class Settings(BaseSettings):
    """
    Application settings with environment-based configuration.
    
    Loads configuration from environment variables and .env files.
    Sensitive values like secrets should never be committed to version control.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application Settings
    app_name: str = Field(default="LMS Backend", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=False, description="Debug mode flag")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(default=8000, description="Server port")
    
    # Database Settings
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/lms",
        description="PostgreSQL async connection URL",
    )
    database_pool_size: int = Field(default=5, description="Database connection pool minimum size")
    database_max_overflow: int = Field(default=20, description="Database connection pool maximum overflow")
    database_pool_timeout: int = Field(default=30, description="Database connection pool timeout in seconds")
    database_echo: bool = Field(default=False, description="Echo SQL queries to stdout")
    
    # JWT Authentication Settings
    jwt_secret_key: str = Field(
        default="your-super-secret-jwt-key-change-in-production",
        description="JWT secret key for token signing",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration in minutes")
    refresh_token_expire_days: int = Field(default=7, description="Refresh token expiration in days")
    
    # CORS Settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated list of allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")
    cors_allow_methods: str = Field(default="GET,POST,PUT,DELETE,PATCH,OPTIONS", description="Allowed HTTP methods")
    cors_allow_headers: str = Field(default="*,Authorization,Content-Type", description="Allowed HTTP headers")
    
    # Redis Settings (for Celery and caching)
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    
    # Email Settings (for notifications)
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_user: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[str] = Field(default=None, description="SMTP password")
    smtp_tls: bool = Field(default=True, description="Use TLS for SMTP")
    email_from: str = Field(default="noreply@lms.local", description="Default sender email")
    
    # File Storage Settings
    upload_dir: str = Field(default="uploads", description="Directory for file uploads")
    max_upload_size: int = Field(default=10 * 1024 * 1024, description="Maximum upload size in bytes (10MB)")
    
    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    
    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @computed_field
    @property
    def cors_allow_methods_list(self) -> list[str]:
        """Parse CORS methods string into a list."""
        return [method.strip() for method in self.cors_allow_methods.split(",") if method.strip()]
    
    @computed_field
    @property
    def cors_allow_headers_list(self) -> list[str]:
        """Parse CORS headers string into a list."""
        return [header.strip() for header in self.cors_allow_headers.split(",") if header.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Get cached Settings instance.
    
    Uses lru_cache to avoid reloading settings on every call.
    Settings are loaded once at application startup.
    
    Returns:
        Settings: Application settings instance
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
