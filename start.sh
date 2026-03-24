#!/bin/bash
# Exit immediately if any command fails
set -e

echo "Starting Production Setup..."

# 1. Apply database migrations
# If the database is not ready (e.g., PostgreSQL is still booting), this script will
# fail and Docker will automatically restart the container until it succeeds.
echo "Applying database migrations..."
python manage.py migrate --noinput

# 2. Start Celery worker in the background
# (In an ideal enterprise microservice setup, you would run this as a separate container.
#  But for simplicity, running it in the background here works perfectly fine.)
echo "Starting Celery worker..."
celery -A crtd worker -l info &

# 3. Start the Django application using Gunicorn
# Using exec ensures Gunicorn takes over PID 1, allowing it to handle Docker shutdown signals gracefully.
# Configured for production with 3 workers and 2 threads.
echo "Starting Gunicorn server..."
exec gunicorn crtd.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
