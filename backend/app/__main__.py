"""
CLI Entry Point for Development Server.

This module provides a command-line interface for running the FastAPI
development server using Uvicorn. It can be invoked with:

    python -m app

Or with explicit host/port:

    python -m app --host 0.0.0.0 --port 8080
"""

import argparse
import sys

import uvicorn

from app.config import get_settings


def main() -> int:
    """
    Main entry point for the development server CLI.
    
    Parses command-line arguments and starts the Uvicorn server
    with the appropriate configuration.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    settings = get_settings()
    
    # Create argument parser
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="LMS Backend Development Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app                    # Run with default settings
  python -m app --host 0.0.0.0     # Bind to all interfaces
  python -m app --port 8080        # Use custom port
  python -m app --reload           # Enable auto-reload on code changes
  python -m app --workers 4        # Run with multiple workers
        """
    )
    
    # Server configuration arguments
    parser.add_argument(
        "--host",
        type=str,
        default=settings.host,
        help=f"Server bind host (default: {settings.host})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help=f"Server port (default: {settings.port})"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=settings.is_development,
        help="Enable auto-reload on code changes (default: True in development)"
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload even in development mode"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1, use 1 for development)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=settings.log_level.lower(),
        choices=["debug", "info", "warning", "error", "critical"],
        help=f"Logging level (default: {settings.log_level.lower()})"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Determine reload setting
    reload_enabled = args.reload and not args.no_reload
    
    # Validate worker count for development
    if args.workers > 1 and reload_enabled:
        print("⚠️  Warning: Using multiple workers with reload enabled.")
        print("   Reload is typically used with a single worker in development.")
    
    # Print startup information
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           LMS Backend Development Server                     ║
╠══════════════════════════════════════════════════════════════╣
║  Environment:  {settings.environment:<46} ║
║  Version:      {settings.app_version:<46} ║
║  Debug Mode:   {str(settings.debug):<46} ║
╠══════════════════════════════════════════════════════════════╣
║  Host:         {args.host:<46} ║
║  Port:         {args.port:<46} ║
║  Reload:       {str(reload_enabled):<46} ║
║  Workers:      {args.workers:<46} ║
║  Log Level:    {args.log_level:<46} ║
╠══════════════════════════════════════════════════════════════╣
║  API Docs:     http://{args.host}:{args.port}/docs{'':<25} ║
║  Health Check: http://{args.host}:{args.port}/health{'':<22} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Start Uvicorn server
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=reload_enabled,
            workers=args.workers,
            log_level=args.log_level,
            # Development-friendly settings
            access_log=True,
            use_colors=True,
            # Graceful shutdown
            lifespan="on",
        )
        return 0
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user.")
        return 0
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
