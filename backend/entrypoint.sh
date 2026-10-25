#!/bin/bash
set -e

# =============================================================================
# Flask Application Entrypoint Script
# =============================================================================
# This script initializes the Flask application for container deployment.
# It performs database initialization, runs migrations, seeds data, and
# starts the Gunicorn server.
#
# Environment Variables:
#   FLASK_ENV: Application environment (development, testing, production)
#   DATABASE_URL: Database connection URL
#   SKIP_MIGRATIONS: Set to 'true' to skip database migrations
#   SKIP_SEED: Set to 'true' to skip database seeding
#   GUNICORN_WORKERS: Number of Gunicorn workers (default: 4)
#   GUNICORN_TIMEOUT: Gunicorn timeout in seconds (default: 120)
# =============================================================================

echo "=========================================="
echo "Flask Application Entrypoint"
echo "=========================================="
echo "Environment: ${FLASK_ENV:-development}"
echo "Time: $(date)"
echo "=========================================="

# Default values
export FLASK_ENV=${FLASK_ENV:-development}
export GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
export GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}
export GUNICORN_BIND=${GUNICORN_BIND:-0.0.0.0:5000}

# Change to the backend directory
cd /workspace/backend || cd /app || true

# =============================================================================
# Database Initialization and Migrations
# =============================================================================

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    echo ""
    echo ">>> Running database migrations..."
    
    # Check if migrations directory exists
    if [ -d "migrations" ]; then
        # Upgrade to the latest migration
        flask db upgrade || alembic upgrade head || echo "Warning: Migration command failed, continuing..."
        echo ">>> Database migrations completed."
    else
        echo ">>> No migrations directory found. Skipping migrations."
        echo ">>> Run 'flask db init' and 'flask db migrate' to create migrations."
    fi
else
    echo ">>> Skipping database migrations (SKIP_MIGRATIONS=true)"
fi

# =============================================================================
# Database Seeding
# =============================================================================

if [ "${SKIP_SEED:-false}" != "true" ]; then
    echo ""
    echo ">>> Seeding database with initial data..."
    
    # Run seed script if it exists
    if [ -f "seed.py" ]; then
        python seed.py || echo "Warning: Seed script failed, continuing..."
    elif [ -f "scripts/seed.py" ]; then
        python scripts/seed.py || echo "Warning: Seed script failed, continuing..."
    else
        echo ">>> No seed script found. Skipping seeding."
    fi
    
    echo ">>> Database seeding completed."
else
    echo ">>> Skipping database seeding (SKIP_SEED=true)"
fi

# =============================================================================
# Start Application Server
# =============================================================================

echo ""
echo ">>> Starting Gunicorn server..."
echo "    Workers: ${GUNICORN_WORKERS}"
echo "    Timeout: ${GUNICORN_TIMEOUT}s"
echo "    Bind: ${GUNICORN_BIND}"
echo ""

# Start Gunicorn with the WSGI application
exec gunicorn \
    --workers "${GUNICORN_WORKERS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --bind "${GUNICORN_BIND}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    --enable-stdio-inheritance \
    --worker-class sync \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    "wsgi:app"
